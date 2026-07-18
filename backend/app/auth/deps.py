"""Dependency: ดึงผู้ใช้ปัจจุบันจาก JWT (Authorization: Bearer <token>)"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth import security

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(cred: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    if cred is None:
        raise HTTPException(401, "ต้องเข้าสู่ระบบก่อน")
    try:
        payload = security.decode_token(cred.credentials)
    except Exception:
        raise HTTPException(401, "โทเคนไม่ถูกต้องหรือหมดอายุ")
    return {"id": int(payload["sub"]), "email": payload.get("email")}
