from datetime import datetime
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools.retriever import create_retriever_tool
from langchain_chroma import Chroma
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from openai import OpenAI
import httpx
from langchain_openai import ChatOpenAI
from langchain_classic.memory import ConversationSummaryBufferMemory

load_dotenv()

@tool
def get_current_time():
    """èŽ·å–å½“å‰ç³»ç»Ÿæ—¶é—´ï¼Œç”¨æˆ·è¯¢é—®æ—¥æœŸã€æ—¶é—´çš„æ—¶å€™è°ƒç”?"""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

@tool
def generate_picture(prompt:str, save_path:str, image_list=None):
    """
    æ ¹æ®æç¤ºè¯ç”Ÿæˆå›¾ç‰‡ï¼Œå¯ä»¥ä¼ å…¥å‚è€ƒå›¾ã€?
    :param prompt: å›¾ç‰‡ç”Ÿæˆæç¤ºè¯?
    :param save_path: å›¾ç‰‡ä¿å­˜æœ¬åœ°è·¯å¾„
    :param image_list: å‚è€ƒå›¾ç‰‡base64æ•°ç»„ï¼Œä¸ºç©ºåˆ™çº¯æ–‡ç”Ÿå›¾
    """
    if image_list is None:
        image_list = []
    extra_body = {}
    if image_list:
        # ç«å±±æ–¹èˆŸé€šè¿‡ extra_body.image ä¼ å‚è€ƒå›¾ï¼ˆURL / base64 æ•°ç»„ï¼?
        extra_body["image"] = image_list
    
    image_client = OpenAI(
        api_key=os.getenv("API_KEY"),
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )
    res = image_client.images.generate(
        prompt=prompt,
        model="doubao-seedream-5-0-lite-260128",
        response_format="url",
        extra_body=extra_body or None,
    )
    url  = res.data[0].url
    image_bytes = httpx.get(url).content
    with open(save_path,"wb") as f:
         f.write(image_bytes)
    return {"success" : True, "path" : save_path}

if __name__ == "__main__":
    embedding = FastEmbedEmbeddings(model_name="BAAI/bge-small-zh-v1.5")
    vector_db = Chroma(
        collection_name= "jihe",
        embedding_function=embedding,
        persist_directory="./langchain_chroma_db"
    )
    retriever = vector_db.as_retriever(search_kwargs={"k" : 3})
    rag_tool = create_retriever_tool(
        retriever,
        name="document search",
        description="å½“ç”¨æˆ·é—®é¢˜éœ€è¦æŸ¥è¯¢æœ¬åœ°æ–‡æ¡£ã€çŸ¥è¯†åº“ã€æ–‡ä»¶èµ„æ–™æ—¶è°ƒç”¨ï¼Œè¿”å›žç›¸å…³æ–‡æ¡£ç‰‡æ®µã€‚ç”¨äºŽæŸ¥æ‰¾ä¸Žé—®é¢˜ç›¸å…³çš„æ–‡ä»¶ä¿¡æ¯ï¼Œæ¯æ¬¡è¿”å›žæœ€ç›¸å…³çš?3æ¡æ–‡æ¡£ç‰‡æ®µã€‚å¦‚æžœéœ€è¦éªŒè¯èµ„æ–™å†…å®¹æˆ–æ‰¾ä¸åˆ°ç›¸å…³ä¿¡æ¯ï¼Œä¸è¦ç¼–é€ ï¼Œç›´æŽ¥è¿”å›žæœªæ‰¾åˆ°ã€?"
    )
    tools= [rag_tool, get_current_time, generate_picture]

    prompt = ChatPromptTemplate.from_messages([
        ("system", "ä½ æ˜¯ä¸€ä¸ªæ™ºèƒ½åŠ©æ‰‹ï¼Œå¯ä»¥æ ¹æ®éœ€æ±‚è°ƒç”¨å·¥å…·ã€‚å›žç­”é—®é¢˜ä¼˜å…ˆä½¿ç”¨æœ¬åœ°æ–‡æ¡£æ£€ç´¢ï¼Œæ²¡æœ‰ä¿¡æ¯å†ä½¿ç”¨å…¶ä»–å·¥å…·ï¼Œä¸è¦ç¼–é€ å†…å®¹ã€‚\nè§„åˆ™ï¼šè°ƒç”¨å·¥å…·å¹¶èŽ·å¾—ç»“æžœåŽï¼Œå¿…é¡»ç«‹å³åŸºäºŽç»“æžœç»™å‡ºæœ€ç»ˆå›žç­”ï¼Œç¦æ­¢é‡å¤è°ƒç”¨åŒä¸€ä¸ªå·¥å…·æˆ–æ— å…³å·¥å…·ï¼›å¦‚æžœå·¥å…·ç»“æžœå·²è¶³å¤Ÿå›žç­”é—®é¢˜ï¼Œä¸è¦å†æ¬¡è°ƒç”¨å·¥å…·ã€?"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    llm = ChatOpenAI(
        openai_api_key=os.getenv("API_KEY"),
        openai_api_base="https://ark.cn-beijing.volces.com/api/coding/v3",
        model="ark-code-latest",
        temperature= 0
    )

    memory  = ConversationSummaryBufferMemory(
        llm = llm,
        max_token_limit = 2000,
        memory_key="chat_history",
        return_messages=True
    )

    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent = agent,
        tools = tools,
        max_iterations = 5,
        memory = memory,
        handle_parsing_errors =True,
        verbose = True
    )
    while True:
        user_input = input("You:")
        if user_input == "exit":
             print("bye,have a good day")
             break
        res = agent_executor.invoke({"input": user_input})
        print(f"Agent:{res}")
