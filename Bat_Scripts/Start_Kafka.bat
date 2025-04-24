@echo off

start cmd /k "cd /d C:\10_Projects\Kafka\kafka && echo Starting Zookeeper... && .\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties"

timeout /t 2 >nul

start cmd /k "cd /d C:\10_Projects\Kafka\kafka && echo Starting Kafka Server... && .\bin\windows\kafka-server-start.bat .\config\server.properties"

exit