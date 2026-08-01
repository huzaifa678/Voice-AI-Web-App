"""Generates docs/infra-architecture.png - the infrastructure / Kubernetes view.
Run from repo root:  ./venv/bin/python docs/generate_infra_diagram.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import EC2
from diagrams.k8s.compute import Pod, StatefulSet
from diagrams.k8s.network import Service, Ingress
from diagrams.k8s.storage import PV
from diagrams.k8s.podconfig import ConfigMap
from diagrams.onprem.database import Postgresql
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.queue import RabbitMQ, Celery
from diagrams.onprem.monitoring import Grafana, Prometheus, Thanos
from diagrams.onprem.tracing import Tempo
from diagrams.onprem.logging import Loki
from diagrams.aws.storage import S3
from diagrams.custom import Custom
import os

L = os.path.abspath("docs/assets/icons")

graph_attr = {
    "bgcolor": "white",
    "fontname": "Helvetica",
    "fontsize": "22",
    "labelloc": "t",
    "pad": "0.6",
    "nodesep": "0.5",
    "ranksep": "1.0",
    "splines": "spline",
}
node_attr = {"fontname": "Helvetica", "fontsize": "12"}
edge_attr = {"fontname": "Helvetica", "fontsize": "11", "color": "#4a5568"}

with Diagram(
    "Voice-AI Web App - Infrastructure (g4dn.xlarge / MicroK8s)",
    filename="docs/infra-architecture",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    ingress = Ingress("ingress-nginx\n(external traffic)")

    with Cluster("AWS S3  —  object storage (long-term)"):
        s3_logs = S3("voice-ai-loki\n(logs)")
        s3_traces = S3("voice-ai-tempo\n(traces)")
        s3_metrics = S3("voice-ai-thanos\n(metrics)")

    with Cluster("AWS EC2  g4dn.xlarge   —   Ubuntu host + MicroK8s"):
        gpu = Custom("NVIDIA GPU (T4)\ntime-sliced -> N vGPUs", f"{L}/nvidia.png")

        with Cluster("namespace: gpu-operator-resources"):
            helm = Custom("Helm release", f"{L}/helm.png")
            gpu_op = Custom("NVIDIA GPU Operator", f"{L}/nvidia.png")
            ts_cfg = ConfigMap("time-slicing-config\n(replicas = slices)")

        with Cluster("namespace: voice-ai"):

            with Cluster("Services (ClusterIP)  —  service host : port"):
                svc_web = Service("voice-ai\n:8000")
                svc_grpc = Service("voice-ai-grpc\n:50051")
                svc_pgb = Service("voice-ai-pgbouncer\n:6432")
                svc_pg = Service("voice-ai-postgresql\n:5432")
                svc_redis = Service("voice-ai-redis-master\n:6379")
                svc_mq = Service("voice-ai-rabbitmq\n:5672")

            with Cluster("Workloads (Pods)"):
                web = Pod("web\nREST + WebSocket\n(uvicorn)")
                grpc = Custom("grpc-stt\nWhisper", f"{L}/grpc.png")
                audio_w = Celery("audio worker")
                tts_w = Custom("tts worker\nXTTS v2", f"{L}/coqui.png")
                pgb = Custom("pgbouncer", f"{L}/pgbouncer.png")
                pg = StatefulSet("postgresql-0")
                pg_db = Postgresql("PostgreSQL")
                redis = Redis("redis-master")
                mq = RabbitMQ("rabbitmq-0")

            with Cluster("Persistent Volumes (PVC)"):
                whisper_pvc = PV("whisper-model-pvc")
                xtts_pvc = PV("xtts-model-pvc")

        with Cluster("namespace: observability"):
            otel = Custom("OpenTelemetry\nCollector", f"{L}/opentelemetry.png")
            loki = Loki("Loki\n(logs)")
            tempo = Tempo("Tempo\n(traces)")
            prom = Prometheus("Prometheus\n(metrics)")
            thanos = Thanos("Thanos\n(store gateway)")
            grafana = Grafana("Grafana\n(dashboards)")

    # external entry
    ingress >> Edge(label="/") >> svc_web

    # service -> backing pod
    svc_web >> web
    svc_grpc >> grpc
    svc_pgb >> pgb
    svc_pg >> pg >> pg_db
    svc_redis >> redis
    svc_mq >> mq

    # app -> data (via services)
    web >> Edge(label="pooled DB") >> svc_pgb
    web >> Edge(label="rate limit") >> svc_redis
    pgb >> Edge(label="upstream :5432") >> svc_pg
    grpc >> Edge(label="publish") >> svc_mq
    audio_w >> Edge(label="consume/publish") >> svc_mq
    tts_w >> Edge(label="consume") >> svc_mq

    # model weights mounted from PVCs
    grpc >> Edge(label="mount /models", style="dashed", color="#805ad5") >> whisper_pvc
    tts_w >> Edge(label="mount /models", style="dashed", color="#805ad5") >> xtts_pvc

    # GPU time-slicing (the important bit)
    helm >> Edge(label="installs", color="#2b6cb0") >> gpu_op
    gpu_op >> Edge(label="applies", color="#2b6cb0") >> ts_cfg
    ts_cfg >> Edge(label="advertises vGPU slices", color="#dd6b20") >> gpu
    grpc >> Edge(label="nvidia.com/gpu: 1 (slice)", color="#38a169") >> gpu
    tts_w >> Edge(label="nvidia.com/gpu: 1 (slice)", color="#38a169") >> gpu

    # observability: app pods export OTLP to the collector
    otel_edge = Edge(label="OTLP", color="#319795")
    web >> Edge(label="OTLP telemetry", color="#319795") >> otel
    grpc >> otel_edge >> otel

    # collector fans out by signal type
    otel >> Edge(label="logs", color="#319795") >> loki
    otel >> Edge(label="traces", color="#319795") >> tempo
    otel >> Edge(label="metrics", color="#319795") >> prom
    prom >> Edge(label="long-term metrics", color="#319795") >> thanos

    # each backend persists to its own S3 bucket
    loki >> Edge(label="writes logs", color="#dd6b20") >> s3_logs
    tempo >> Edge(label="writes traces", color="#dd6b20") >> s3_traces
    thanos >> Edge(label="writes metrics", color="#dd6b20") >> s3_metrics

    # Grafana reads all three data sources
    grafana >> Edge(label="query", style="dashed", color="#805ad5") >> loki
    grafana >> Edge(style="dashed", color="#805ad5") >> tempo
    grafana >> Edge(label="query", style="dashed", color="#805ad5") >> thanos
