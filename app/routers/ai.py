"""
AI proxy endpoint
"""
import os
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
import anthropic

client = anthropic.Anthropic()

router = APIRouter()

class AIRequest(BaseModel):
    prompt: str

@router.post("/recommend")
async def get_recommendation(req: AIRequest):
    print(f"req.prompt: {req.prompt}")


    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": req.prompt}
        ]
    )
    print(message.content)
    return message.content
     
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(
    #         "https://api.anthropic.com/v1/messages",
    #         headers={
    #             "x-api-key": api_key,
    #             "anthropic-version": "2023-06-01",
    #             "content-type": "application/json",
    #         },
    #         json={
    #             "model": "claude-sonnet-4-20250514",
    #             "max_tokens": 1000,
    #             "messages": [{"role": "user", "content": req.prompt}],
    #         },
    #         timeout=30,
    #     )
    #     print(response)
    #     return response.json()