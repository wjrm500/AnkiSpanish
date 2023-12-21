@echo off
SETLOCAL

REM Define the path to the virtual environment activation script
SET "VENV_PATH=.\venv\Scripts\activate.bat"

REM Activate the virtual environment
echo Activating virtual environment...
call "%VENV_PATH%"

REM Run isort
echo Running isort...
isort .\app .\test --check-only > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

REM Run black
echo Running black...
black .\app .\test --check > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

REM Run flake8
echo Running flake8...
flake8 .\app .\test > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

REM Run mypy
echo Running mypy...
mypy .\app --strict > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

REM Run pytest
echo Running pytest...
pytest .\test > NUL 2>&1
IF %ERRORLEVEL% EQU 0 (echo SUCCESS) ELSE (echo FAILURE)

ENDLOCAL
