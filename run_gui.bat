@echo off
title KI USA - Plex ERP Importer GUI
echo.
echo ==========================================================
echo           KI USA - Plex ERP Importer GUI
echo ==========================================================
echo.
echo Iniciando aplicacion Streamlit...
echo Para cerrar la aplicacion, cierre esta ventana o presione Ctrl+C.
echo.
python -m streamlit run gui/app.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo Ocurrio un error al iniciar la aplicacion. Asegurese de que
    echo streamlit y las dependencias esten correctamente instaladas.
    echo.
    pause
)
