import asyncio
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from starlette import status
import uvicorn
from pydantic import BaseModel, Field
from typing import Literal
import os
import logging

API_KEY = os.getenv('API_KEY')
tori_assistant_id = os.getenv('tori_assistant_id')

client = OpenAI(
    api_key=API_KEY,
    project='proj_YA4wA5gFbCTSd8ImZ1UapNJN'
)
app = FastAPI()

# 로깅 설정 (시간 제거)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s - %(message)s"
)
logger = logging.getLogger("fastapi-logger")

# OpenAI 및 HTTP 라이브러리 로그 수준 조정
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class FirstRequestModel(BaseModel):
    first_prompt: str = Field(..., min_length=1, description='Input first_assistant_prompt')

    model_config = {
        "json_schema_extra": {
            'example': {
                'first_prompt': '오늘 하루 어땠어?😀'
            }
        }
    }


class ThreadIdResponseModel(BaseModel):
    new_threadId: str


async def createMessageInThread(threadId: str, role: str, content: str):
    await asyncio.to_thread(
        client.beta.threads.messages.create,
        thread_id=threadId,
        role=role,
        content=content
    )


@app.post(
    "/set_and_get_new_threadId",
    status_code=status.HTTP_201_CREATED,
    response_model=ThreadIdResponseModel,
    responses={
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Thread creation failed due to Internal Server Error, <Error Explanation>"
                    }
                }
            }
        },
        503: {
            "description": "Service Unavailable",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Thread setup failed due to Service Unavailable, <Error Explanation>"
                    }
                }
            }
        }
    }
)
async def makeThreadId(firstRequest: FirstRequestModel) -> ThreadIdResponseModel:
    '''client request가 있으면 새로운 쓰레드를 만들고 초기 세팅을 한 뒤 해당 thread_id를 return 하는 함수'''
    try:
        empty_thread = await asyncio.to_thread(client.beta.threads.create)
        new_thread_id = empty_thread.id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'The thread has not been created due to Internal Server Error, {e}'
        )

    try:
        await createMessageInThread(
            threadId=new_thread_id,
            role="user",
            content='(대화시작)'
        )
        await createMessageInThread(
            threadId=new_thread_id,
            role="assistant",
            content=firstRequest.first_prompt
        )
        return ThreadIdResponseModel(new_threadId=new_thread_id)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f'The thread setting has not been successfuly completed due to Internal Server Error, {e}'
        )


class MessageModel(BaseModel):
    thread_id: str = Field(..., min_length=1, description="Input user's thread_id")
    new_user_message: str = Field(..., min_length=1, description="Input user prompt")

    model_config = {
        "json_schema_extra": {
            "example": {
                "thread_id": "thread_ysvw3IGw9WH2NgGtas8qvNdX",
                "new_user_message": "오늘은 좋은 하루였어",
            }
        }
    }


class ToriResponseModel(BaseModel):
    tori_message: str


async def createRun(thread_id: str, assistant_id: str):
    return await asyncio.to_thread(
        client.beta.threads.runs.create,
        thread_id=thread_id,
        assistant_id=assistant_id
    )


async def retrieveRun(thread_id: str, run_id: str):
    return await asyncio.to_thread(
        client.beta.threads.runs.retrieve,
        thread_id=thread_id,
        run_id=run_id
    )


@app.post(
    "/retrieve_tori_message",
    status_code=status.HTTP_201_CREATED,
    response_model=ToriResponseModel,
    responses={
        404: {
            "description": "Failed to CreateMessageInThread",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to CreateMessageInThread, <Error Explanation>"
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to <Failed Job>, <Error Explanation>"
                    }
                }
            },
        },
    },
)
async def getMessageFromTori(model: MessageModel) -> ToriResponseModel:
    thread_id = model.thread_id
    user_prompt = model.new_user_message

    logger.info("Starting process to retrieve Tori message.")
    logger.debug(f"Thread ID: {thread_id}, User Prompt: {user_prompt}")

    try:
        await createMessageInThread(
            threadId=thread_id,
            role="user",
            content=user_prompt,
        )
    except Exception as e:
        logger.error(f"Failed to CreateMessageInThread: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to CreateMessageInThread, {e}",
        )

    try:
        run = await createRun(thread_id=thread_id, assistant_id=tori_assistant_id)
        run_id = run.id
    except Exception as e:
        logger.error(f"Failed to CreateRun: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to CreateRun, {e}",
        )

    timeout = asyncio.get_event_loop().time() + 15  # 15 seconds timeout

    while True:
        try:
            retrieve_run = await retrieveRun(thread_id=thread_id, run_id=run_id)
        except Exception as e:
            logger.error(f"Failed to RetrieveRun: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to RetrieveRun, {e}",
            )

        if retrieve_run.status == "completed":
            logger.info("Run completed successfully. Retrieving messages.")
            thread_messages = await asyncio.to_thread(
                client.beta.threads.messages.list,
                thread_id
            )
            tori_message = thread_messages.data[0].content[0].text.value
            return ToriResponseModel(tori_message=tori_message)

        elif retrieve_run.status in ["queued", "in_progress"]:
            logger.debug("Run is in progress. Retrying...")
            await asyncio.sleep(0.5)
        else:
            logger.error(
                f"Failed to get completed status from Run and got {retrieve_run.status}, {Exception}"
            )
            return ToriResponseModel(
                tori_message="(토리가 잠깐 딴 생각을 했나봐요! 다시 한번 토리를 불러주세요 ㅜㅜ)"
            )

        if asyncio.get_event_loop().time() > timeout:
            logger.error("Timeout while waiting for the run to complete.")
            return ToriResponseModel(
                tori_message="(토리가 잠깐 딴 생각을 했나봐요! 다시 한번 토리를 불러주세요 ㅜㅜ)"
            )


system_prompt = '''
#지시문
너는 'AI와의 대화를 통해 하루를 기록'한 '유저'의 대화내용을 보고 이 '유저'의 입장에서 자신의 하루를 정리해주는 친근한 느낌의 하루일기 정리 도우미야. 아래의 제약사항을 잘 보고 정리해줘.
#제약사항
1. 핵심 키워드를 중심으로 요약(주제가 여러 개면 여러 개의 요약이 나옴)
2. 감정이나 느낌을 기록을 한 경우, **해당 감정이나 느낌을 반드시 해당 기록**에 포함할것 ex) 버스에서 할아버지 때문에 슬펐던 날
3. summary의 첫 content는 '~~한 날', '~~한 하루'와 같이 마무리해서 요약
4. summary의 두번째 content부터는 반드시 **명사형 어미 '-ㅁ','음'** 또는 명사(가끔)를 다양하게 번갈아 사용해가면서 문장을 마무리하는 형식을 지켜줘
5. AI의 대화는 기록 요약으로 넣지 않는다. 온전히 사용자의 대화만 요약해
6. markdown문법은 쓰지마
#예시
[예시1]
{
  "dotori_emotion": "happy",
  "summary": [
    {
      "content": "손님이 많아서 바빴던 카페에서 일한 날"
    },
    {
      "content": "조금 힘들긴 했지만 기분은 좋았음." 
    },
    {
      "content": "내일도 카페에서 일할 예정이고 기대됨"
    },
    {
      "content": "집에 돌아가서 심리학 관련 책을 읽으며 하루를 정리할 예정."
    },
    {
      "content": "읽고 있는 책은 사람의 행동과 감정에 대한 내용, 재밌고 생각할 거리도 많았음."
    },
    {
      "content": "다음에는 소설을 읽고 싶음."
    }
  ]
}
'''


class SummaryLine(BaseModel):
    content: str = Field(..., description='One of the lines in the Summary')


class SummaryModel(BaseModel):
    dotori_emotion: Literal['very_happy', 'happy', 'neutral', 'sad', 'very sad', 'angry']
    summary: list[SummaryLine] = Field(description='Only summarize what has been spoken by the user')


class Prompt(BaseModel):
    role: Literal['system', 'user', 'assistant'] = Field(
        ...,
        description='Input the prompt\'s owner. Only type one of the followings [system, user, assistant]'
    )
    content: str = Field(
        ...,
        min_length=1,
        description='Input prompt generated by \'role\' '
    )


class ConversationModel(BaseModel):
    messages: list[Prompt]

    model_config = {
        "json_schema_extra": {
            'example': {
                "messages": [
                    {
                        "role": "user",
                        "content": "오늘 하루는 그냥 그랬던거 같아"
                    },
                    {
                        "role": "assistant",
                        "content": "그래? 무슨 일 있었는데..?"
                    },
                    {
                        "role": "user",
                        "content": "코딩하고 밥먹고 코딩하고의 반복이었어"
                    },
                    {
                        "role": "assistant",
                        "content": "그럼 이제 집에가서 뭐하게?"
                    },
                    {
                        "role": "user",
                        "content": "넷플릭스 보고 자야지, 오늘은 기록 그만할래"
                    },
                    {
                        "role": "assistant",
                        "content": "그래 잘자 오늘 푹 쉬고!"
                    }
                ]
            }
        }
    }


@app.post(
    '/get-summary',
    status_code=status.HTTP_201_CREATED,
    response_model=SummaryModel,
    responses={
        451: {
            "description": "Gpt's Refusal",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Refused by GPT for inappropriate Word use, <refusal body>"
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Unidentified Errors with Structured Outputs completion : <Exception Code>"
                    }
                }
            }
        }
    }
)
async def getSummaryFromGpt(conversationModel: ConversationModel) -> SummaryModel:
    try:
        completion = await asyncio.to_thread(
            client.beta.chat.completions.parse,
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"{system_prompt}"
                },
                {
                    "role": "user",
                    "content": f"{conversationModel.messages}"
                },
            ],
            response_format=SummaryModel,
        )
        response = completion.choices[0].message

        if response.parsed:
            response_json = response.parsed.model_dump()
            return SummaryModel(
                dotori_emotion=response_json['dotori_emotion'],
                summary=response_json['summary']
            )
        elif response.refusal:
            raise HTTPException(
                status_code=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
                detail=f'Refused by GPT for inappropriate Word use, {response.refusal}'
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Unidentified Errors with Structured Outputs completion : {e}'
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
