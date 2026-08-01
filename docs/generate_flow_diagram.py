"""Generates docs/architecture-flow.png - the application-level data flow.
Run from repo root:  ./venv/bin/python docs/generate_flow_diagram.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import Users
from diagrams.onprem.database import Postgresql
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.queue import RabbitMQ, Celery
from diagrams.programming.framework import Django, Nextjs
from diagrams.custom import Custom
import os

L = os.path.abspath("docs/assets/icons")

graph_attr = {
    "bgcolor": "white",
    "fontname": "Helvetica",
    "fontsize": "22",
    "labelloc": "t",
    "pad": "0.75",
    "nodesep": "0.9",
    "ranksep": "1.5",
    "splines": "spline",
    "concentrate": "false",
}
node_attr = {"fontname": "Helvetica", "fontsize": "12", "margin": "0.16,0.12"}
edge_attr = {"fontname": "Helvetica", "fontsize": "11", "color": "#4a5568"}

with Diagram(
    "Voice-AI Web App - Application Flow",
    filename="docs/architecture-flow",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    user = Users("User\n(browser mic)")

    with Cluster("Frontend (Next.js)"):
        fe = Nextjs("Web UI\nregister / login\naudio stream")

    with Cluster("Django Backend (REST + WebSocket + gRPC)"):
        rest = Django("REST API\nauth / sessions")
        ws = Django("WebSocket\nhandler")
        redis = Redis("Redis\nrate limiting")
        vad = Custom("Silero VAD", f"{L}/silero.png")

        with Cluster("STT"):
            grpc = Custom("gRPC servicer", f"{L}/grpc.png")
            whisper = Custom("Whisper", f"{L}/whisper.png")

    with Cluster("Message Queue"):
        mq = RabbitMQ("RabbitMQ\nSTT / LLM / TTS / email")

    with Cluster("Workers"):
        llm_worker = Celery("LLM worker")
        tts_worker = Celery("TTS worker")

    with Cluster("AI Models"):
        llm = Custom("Llama 3.3\nvia Groq", f"{L}/groq.png")
        tts = Custom("XTTS v2\ntext-to-speech", f"{L}/coqui.png")

    with Cluster("Data (connection pooled)"):
        pgb = Custom("PgBouncer\n:6432", f"{L}/pgbouncer.png")
        pg = Postgresql("PostgreSQL\nusers + chat sessions")

    # 1. auth + persistence
    user >> Edge(label="1. register / login\n+ mic audio") >> fe
    fe >> Edge(label="REST") >> rest
    rest >> Edge(label="rate limit") >> redis
    rest >> Edge(label="pooled") >> pgb >> Edge(label=":5432") >> pg

    # 2-3. speech in -> VAD -> STT
    fe >> Edge(label="2. WS audio stream") >> ws
    ws >> Edge(label="probability") >> vad
    vad >> Edge(label="3. speech buffer") >> grpc
    grpc >> Edge(label="transcribe") >> whisper
    whisper >> Edge(label="transcript") >> mq

    # 4. LLM
    mq >> Edge(label="4. STT msg") >> llm_worker
    llm_worker >> Edge(label="prompt") >> llm
    llm >> Edge(label="response") >> llm_worker
    llm_worker >> Edge(label="LLM + TTS queues") >> mq

    # 5. LLM response back to UI
    mq >> Edge(label="5. LLM response") >> ws
    ws >> Edge(label="text + audio") >> fe

    # 6. TTS
    mq >> Edge(label="6. TTS task") >> tts_worker
    tts_worker >> Edge(label="synthesize") >> tts
    tts >> Edge(label="audio") >> tts_worker
    tts_worker >> Edge(label="audio reply") >> ws
