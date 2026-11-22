@echo off
setlocal DisableDelayedExpansion
if not exist "%~dp0native-menu\install.ps1" goto incomplete
pushd "%~dp0" || goto location_failed
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0native-menu\install.ps1" %*
set "TOKENBOTS_INSTALL_CODE=%ERRORLEVEL%"
popd
if not "%TOKENBOTS_INSTALL_CODE%"=="0" echo Installation stopped. Keep the error text; do not send your Key.
goto finished
:incomplete
echo [INCOMPLETE_PACKAGE] The native-menu folder must be beside install-native.cmd.
echo Right-click the ZIP and choose Extract All, then run from the extracted folder.
echo Do not run inside the ZIP or copy only this CMD file to the Desktop.
set "TOKENBOTS_INSTALL_CODE=1"
goto finished
:location_failed
echo [INSTALL_FOLDER] Cannot open the installer folder. Extract the full ZIP to a local folder.
set "TOKENBOTS_INSTALL_CODE=1"
:finished
if not "%TOKENBOTS_INSTALL_NO_PAUSE%"=="1" pause
exit /b %TOKENBOTS_INSTALL_CODE%
