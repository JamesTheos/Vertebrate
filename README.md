# Vertebrate
Industrial Data Centric Tech Stack




# Installation:
 
 - OPTIONAL for Frontend: create a Win11 or Server 2022 VM that can run VMs (https://learn.microsoft.com/en-us/virtualization/hyper-v-on-windows/user-guide/enable-nested-virtualization)
 - create a folder in C: called 10_Projects where all the project files will be (PLC; kafka,...)
 - OPTIONAL for Frontend: download and install codesys control win to be able to program and engineer a PLC (https://store.codesys.com/en/codesys-control-win-sl-1.html)
 - OPTIONAL for Frontend: install vscode (https://code.visualstudio.com/)
 - install github desktop and subscribe to our repo and use VScode as the editor
 - install docker desktop (https://www.docker.com/products/docker-desktop/)
 - download the Kafka UI container from Github (https://github.com/provectus/kafka-ui)
 - Install Python from MS store
 - Download Kafka Scala 2.13   to run the zookeeper and broker (https://kafka.apache.org/downloads) - currently apps running from the terminal
 -   for Kafka: the folders must be like this:
      * for Kafka zookeper properties: dataDir=C:/10_Projects/Kafka/zookeeper
      * for KAFKA BROKER properties: log.dirs=C:/10_Projects/Kafka/kafka-logs
       
 - install/update Java JavaSetup8u421
 - OPTIONAL for Frontend: install UAexpert OPC viewer to be able to see and manupliate PLC data for testing

 for Vertebrate project, we need extra libraries
 on terminal run:  
   - pip install opcua confluent_kafka
   - pip install Flask

# Running the Program

--------------Kafka - Terminal --------------
C:\10_Projects\Kafka\kafka
- .\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties
- .\bin\windows\kafka-server-start.bat .\config\server.properties

--------------Kafka UI - Docker --------------
Run the Docker for the Kafka UI
- Kafka UI Container: http://localhost:8080/

- Cluster ID = **<check the kafka log>**  # was rYljdbXyQDSKW0su40H0kA
- from now on will use node **<check the kafka log>**:9092

--------------PLC - Taskbar --------------
- make sure the plc is running
- open UAexpert and subscribe to the programs tags

--------------Kafka producer and consumer - VScode --------------
- Run the producer PLCtoKafka python app
- Run the consumer App.py app 
- open trending at http://localhost:5000/
 
 
