@echo off

set folder1=C:\10_Projects\Kafka\kafka\logs
set folder2=C:\10_Projects\Kafka\kafka-logs
set folder3=C:\10_Projects\Kafka\zookeeper\version-2


echo Deleting contents of %folder1%...
del /q "%folder1%\*" >nul 2>&1
for /d %%i in ("%folder1%\*") do rd /s /q "%%i"

echo Deleting contents of %folder2%...
del /q "%folder2%\*" >nul 2>&1
for /d %%i in ("%folder2%\*") do rd /s /q "%%i"

echo Deleting contents of %folder3%...
del /q "%folder3%\*" >nul 2>&1
for /d %%i in ("%folder3%\*") do rd /s /q "%%i"

echo Deleted everything in %folder1%, %folder2% and %folder3%.


pause