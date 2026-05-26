@echo off
REM ============================================================
REM get_parsed_args Interactive Examples Runner
REM ============================================================
REM
REM This script runs the interactive tutorials for get_parsed_args.
REM Each tutorial explains what the code does, shows expected
REM behavior, and lets you observe the results.
REM
REM Usage:
REM   run_examples.bat              - Show menu
REM   run_examples.bat basic        - Run basic usage tutorial
REM   run_examples.bat types        - Run type handling tutorial
REM   run_examples.bat presets      - Run presets tutorial
REM   run_examples.bat all          - Run all tutorials
REM
REM ============================================================

setlocal enabledelayedexpansion

REM Change to the SciencePythonUtils root directory
cd /d "%~dp0\..\..\..\.."

REM Set PYTHONPATH
set PYTHONPATH=src

REM Get the examples directory
set EXAMPLES_DIR=examples\rich_python_utils\common_utils\arg_utils

if "%1"=="" goto menu
if "%1"=="basic" goto basic
if "%1"=="types" goto types
if "%1"=="presets" goto presets
if "%1"=="all" goto all
if "%1"=="help" goto help
goto menu

:menu
echo.
echo ============================================================
echo   GET_PARSED_ARGS INTERACTIVE TUTORIALS
echo ============================================================
echo.
echo Choose a tutorial to run:
echo.
echo   1. Basic Usage    - Learn the different input formats
echo   2. Type Handling  - Boolean, list, dict, tuple handling
echo   3. Presets        - Configuration file system
echo   4. All Tutorials  - Run all tutorials in sequence
echo   5. Exit
echo.
set /p choice="Enter choice (1-5): "

if "%choice%"=="1" goto basic
if "%choice%"=="2" goto types
if "%choice%"=="3" goto presets
if "%choice%"=="4" goto all
if "%choice%"=="5" goto end
goto menu

:basic
echo.
echo ============================================================
echo   STARTING: Basic Usage Tutorial
echo ============================================================
echo.
python %EXAMPLES_DIR%\example_basic_usage.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Failed to run example. Make sure Python is installed.
    pause
)
goto end

:types
echo.
echo ============================================================
echo   STARTING: Type Handling Tutorial
echo ============================================================
echo.
python %EXAMPLES_DIR%\example_type_handling.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Failed to run example. Make sure Python is installed.
    pause
)
goto end

:presets
echo.
echo ============================================================
echo   STARTING: Presets Tutorial
echo ============================================================
echo.
python %EXAMPLES_DIR%\example_presets.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Failed to run example. Make sure Python is installed.
    pause
)
goto end

:all
echo.
echo ============================================================
echo   RUNNING ALL TUTORIALS
echo ============================================================
echo.
echo Tutorial 1/3: Basic Usage
echo ============================================================
python %EXAMPLES_DIR%\example_basic_usage.py
echo.
echo.
echo ============================================================
echo Tutorial 2/3: Type Handling
echo ============================================================
python %EXAMPLES_DIR%\example_type_handling.py
echo.
echo.
echo ============================================================
echo Tutorial 3/3: Presets
echo ============================================================
python %EXAMPLES_DIR%\example_presets.py
echo.
echo ============================================================
echo   ALL TUTORIALS COMPLETE!
echo ============================================================
goto end

:help
echo.
echo Usage: run_examples.bat [option]
echo.
echo Options:
echo   (none)    Show interactive menu
echo   basic     Run basic usage tutorial
echo   types     Run type handling tutorial
echo   presets   Run presets tutorial
echo   all       Run all tutorials
echo   help      Show this help
echo.
goto end

:end
endlocal
