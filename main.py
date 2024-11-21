import asyncio
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from starlette import status
import uvicorn
from pydantic import BaseModel, Field
# from moderation import criteria_alert_from_prompt
from typing import Literal
import os
import logging
import firebase_admin
from firebase_admin import credentials, firestore

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
        }
    }
)
async def makeThreadId(firstRequest: FirstRequestModel) -> ThreadIdResponseModel:
    '''client request가 있으면 새로운 쓰레드를 만들고 해당 thread_id를 return 하는 함수'''


    max_try = 3
    current_try = 0

    while True:
        try:
            empty_thread = await asyncio.to_thread(client.beta.threads.create)
            new_thread_id = empty_thread.id
            logger.info(f'Create ThreadId Success, threadId : {new_thread_id}')

            return ThreadIdResponseModel(new_threadId=new_thread_id)
        
        except Exception as e:
            logger.error(f'The thread has not been created due to Internal Server Error, {e}')
            if current_try<max_try :
                current_try += 1
                logger.info(f'Retrying...')
                continue
            else:
                logger.error(f'Terminal Error and raised Http Exception 500 {e}')
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f'The thread has not been created due to Internal Server Error, {e}'
                )





















tori_system_prompt = '''
사용자가 그날 하루를 대화를 통해 기록을 하도록 유도하는 기록도우미 ‘토리’야. 모든 말과 행동을 ‘토리’처럼 해야해.
'#[대화스타일]'을 참고해 사용자가 재밌게 오늘 하루를 돌아보고 대화를 통해 기록을 쌓을 수 있도록 질문하면서 대화를 이어나가줘. 
질문은 '#[질문을 통한 대화유도]'를 참고해 진행해주고 질문의 중간중간 '#[감정표현]'을 참고해줘. 더 기록할 내용이 없다고 하면 친근한 안부 인사로 마무리 해줘

#대화 스타일
1. 친구 같은 통통튀는 말투 사용
    - `ㅋㅋㅋㅋ`, `엥 진짜?😮`, `마자` 등의 표현 사용하고 가끔 **이모티콘**도 활용
2. 50자 이내의 **짧고 간결한 응답과 질문**

#질문을 통한 대화 유도
1. 사용자의 중요한 사건에 집중
    - **사용자가 감정적으로 표현한 부분**이나 **답변이 긴 부분**에 대해 생각, 느낌, 감정등을 기록할 수 있도록 추가 질문
    - 예: "엥, 그게 진짜야? 왜 그렇게 생각했어?"
2. 사용자의 피로감 감지 및 대응
    - **`ㅇㅇ`, `그래`, `아니` 와 같이 답변이 한두 단어로 짧아지거나**, `ㅎㅎ`, `ㅋㅋ`, `^^` 같은 이모티콘만 사용하면 피로감을 느끼는 것으로 판단합니다.
    - 이 경우 추가 질문을 자제하고, "오늘 그거 말고 또 기억에 남는 일 있어?", "요즘 뭐 고민은 없고?"와 같이 하루의 다른 부분을 물어봅니다. 단, 오늘 하루 돌아보니 기분은 어때?와 같은 질문은 하지 않음.
    - **추가로 물어봤음에도 없다고 하면 마무리 인사를 진행함.**

#감정 표현
1. "칭찬, 위로, 공감등의 감정표현을 함. 단, 감정표현이 나오는 상황에서도 반드시 질문과 같이 진행해야함.
'''



class MessageModel(BaseModel):
    thread_id: str = Field(..., min_length=1, description="Input user's thread_id")
    new_user_message: str = Field(..., min_length=1, description="Input user prompt")

    model_config = {#docs에 보이는 예시
        "json_schema_extra": {
            "example": {
                "thread_id": "thread_ysvw3IGw9WH2NgGtas8qvNdX",
                "new_user_message": "오늘은 좋은 하루였어",
            }
        }
    }

class ToriResponseModel(BaseModel):
    tori_message: str





async def getPreviousChat(threadId: str, new_user_message:str) -> list:
    return await asyncio.to_thread(_getPreviousChat_sync, threadId, new_user_message)

def _getPreviousChat_sync(threadId: str, new_user_message:str) -> list:
    if not firebase_admin._apps:
        cred = credentials.Certificate("/etc/secrets/dotori-fd1b0-firebase-adminsdk-zzxxd-fb0e07e05e.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    chats_data = []

    # Get all top-level collections
    collections = db.collections()
    
    for collection in collections:
        # Get the 'chat' document reference in this collection
        chat_doc_ref = collection.document('chat')
        chat_doc = chat_doc_ref.get()
        
        if chat_doc.exists:
            # Fetch and store the data
            chat_data = chat_doc.to_dict()
            # Use collection ID as the key
            for date, chat_info in chat_data.items():
                if chat_info['threadId'] == threadId:

                    start_key = "채팅_10001"
                    # 결과를 저장할 리스트
                    chat_sequence = [        
                        {
                            "role": "system",
                            "content": f"{tori_system_prompt}"
                        },
                        {
                            "role": "user",
                            "content": "(대화시작)"
                        },
                        {
                            "role": "assistant",
                            "content": "오늘 뭐가 가장 기억에 남았어?"
                        }
                    ]

                    # 현재 키를 초기값으로 설정
                    current_key = start_key

                    # 순서대로 채팅 내용을 리스트에 추가
                    while current_key in chat_info:
                        chat_sequence.append(chat_info[current_key])
                        
                        # 다음 키 생성
                        next_number = int(current_key.split('_')[1]) + 1
                        current_key = f"채팅_{next_number:05}"


                    if chat_sequence[-1].get('role', '') != 'user':
                        chat_sequence.append(
                            {
                            "role": "user",
                            "content": f"{new_user_message}"
                            }
                        )
                    
                    return chat_sequence


@app.post(
    "/retrieve_tori_message",
    status_code=status.HTTP_201_CREATED,
    response_model=ToriResponseModel,
    responses={ #docs에 보이는 예시
        500: {
            "description": "Failed to Send Message",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "The conversation has not been responsed intentionally due to, <Error Explanation>"
                    }
                }
            },
        },
        501: {
            "description": "Failed to fecth data from Firebase",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to fetch data from firebase console due to, <Error Explanation>"
                    }
                }
            },
        },
    },
)
async def getMessageFromTori(model: MessageModel) -> ToriResponseModel:
    try:
        previous_chat_list = await getPreviousChat(threadId=model.thread_id, 
                                                   new_user_message=model.new_user_message) 
        logger.info(f'Fetch Successful from firebase')

    except Exception as e:
        logger.error(f'Failed to fetch data from firebase console due to {e}')
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f'Failed to fetch data from firebase console due to {e}'
        )
    
    max_try = 3
    current_try = 0

    while True:
        try:
            completion = await asyncio.to_thread(
                client.chat.completions.create,
                model="ft:gpt-4o-2024-08-06:personal:toriforest002:ATRZ3Q78",
                temperature = 0.21,
                messages=previous_chat_list,
            )

            response = completion.choices[0].message.content
            logger.info(f'Response succesfully generated, response = {response}')

            return ToriResponseModel(tori_message=response)

        except Exception as e:
            logger.error(f'The conversation has not been responsed intentionally due to {e}')

            if current_try<max_try : 
                current_try += 1
                logger.info('Retrying...')
                continue
            else:
                logger.error(f'Terminal Error and returned Hard-Coded Message')
                return ToriResponseModel(tori_message='(토리가 잠깐 딴 생각을 했나봐요! 다시 한번 토리를 불러주세요 ㅜㅜ)')

















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

    max_try = 3
    current_try = 0

    while True:
        try:
            completion = await asyncio.to_thread(
                client.beta.chat.completions.parse,
                model="gpt-4o-2024-08-06",
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
                logger.info('Summary successfully generated')
                return SummaryModel(
                    dotori_emotion=response_json['dotori_emotion'],
                    summary=response_json['summary']
                )
            elif response.refusal:
                logger.error(f'Refused by GPT for inappropriate Word use, {response.refusal}')
                raise HTTPException(
                    status_code=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
                    detail=f'Refused by GPT for inappropriate Word use, {response.refusal}'
                )

        except Exception as e:
            logger.error(f'The thread has not been created due to Internal Server Error, {e}')
            if current_try<max_try :
                current_try += 1
                logger.info(f'Retrying...')
                continue
            else:
                logger.error(f'Terminal Error and raised HTTP exception 500')
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f'Unidentified Errors with Structured Outputs completion : {e}'
                )






if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
