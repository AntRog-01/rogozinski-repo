# ai-generated: 90% - Semgrep test cases for direct-sqlite-connect and jsonresponse-status-404
import sqlite3
from fastapi import status
from fastapi.responses import JSONResponse


def bad_db():
    # ruleid: direct-sqlite-connect
    conn = sqlite3.connect("test.db")
    return conn


def good_db(get_connection):
    # ok: direct-sqlite-connect
    conn = get_connection()
    return conn


def bad_response():
    # ruleid: jsonresponse-status-404
    return JSONResponse(status_code=404, content={"error": "not found"})


def good_response():
    # ok: jsonresponse-status-404
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "not found"})
