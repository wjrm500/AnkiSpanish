@echo off
SETLOCAL

REM Define the path to the virtual environment activation script
SET "VENV_PATH=.\venv-dev\Scripts\activate.bat"

REM Activate the virtual environment
echo Activating virtual environment...
call "%VENV_PATH%"

REM Run isort
echo Running isort...
isort .\src --check-only > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

REM Run black
echo Running black...
black .\src --check > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

REM Run flake8
echo Running flake8...
flake8 .\src > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

REM Run mypy
echo Running mypy...
mypy .\src --strict > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

ENDLOCAL
