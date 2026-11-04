@echo off
REM 一键注入本机环境变量（读取 .env 的 VAR=VALUE 行并 set）
REM 用法：call setenv_local.cmd
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0.env") do (
    set "%%A=%%B"
)
echo [setenv_local] environment variables loaded:
set LIT
set CHROME
set CDP
set QUEUE_PATH
set WORKSPACE
