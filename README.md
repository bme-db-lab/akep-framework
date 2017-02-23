# AKÉP

## INSTALL
Copy akep-framework\src\framework\akep.cfg.sample to akep-framework\src\framework\akep.cfg

## RUN

```shell
python3 main.py [-p CONF_PATH] [-l LOG_PATH] [-s ECERCISE_SCHEMA_PATH] [-c CHANNEL_INPUT_SCHEMA_PATH]
```

**CONF_PATH**: Local config file. \(str, opt, def='./akep.local.cfg'\)

**LOG_PATH**: Main log file path, and all log file will store to this path. \(str, req, def='./log/akep.log'\)

**ECERCISE_SCHEMA_PATH**: Task desctiption file schema \(str,req,def='../schema/akep-exercises.xsd'\)

**CHANNEL_INPUT_SCHEMA_PATH**: AKÉP Task channel output schema file \(str, opt, def: '../schema/akep-XMLChannel.xsd'\)

### RUN scenario:
1.	Run the above command. (IF AKÉP does not find akep.cfg, will be terminated)
2.	akep.cfg has port, and interface to configure the AKÉP socket listening
3.	Send a command to this socket with e.g.  nc localhost 5555

### Commands (after connection success)
-	Task submission in JSON object:
	`{"ownerID":"user","exerciseID":"id to exercisesPath/exercise.ID.xml","solutionDir":"the target strudent solution file path"}`
-	Socket close: AKÉP will close socket automatic after send the result in this socket.

### AKEP.cfg
- "host":"interface",
- "port": port,
- "exercisesPath":"Task desctiption file path",
- "notCopyFromDescrtiption":["script","info","exerciseKeys"] -> ezeket a tag-eket nem teszi bele az értékelés utáni kimenetbe a feladatleíróból
}

Detailed description coming soon...
