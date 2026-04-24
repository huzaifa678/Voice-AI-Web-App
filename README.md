# Voice-AI-Web-App

![CI](https://github.com/huzaifa678/Voice-AI-Web-App/actions/workflows/ci.yml/badge.svg)
![E2E Tests](https://img.shields.io/badge/E2E%20Tests-Passing-brightgreen)
![Integration Tests](https://img.shields.io/badge/Integration%20Tests-Passing-brightgreen)

## General Flow of the Web App:

1. User registers -> User login -> DB store via postgres

2. User speaks to the browser mic -> Websocket listens and process the audio -> sends to Silero VAD evaluating the probability

3. Based on the threshold the audio buffer is passed to the gRPC servicer -> the servicer calls Whisper to Speech to Text Conversion -> The converted text is published to the RabbitMQ queue

4. The worker subscribed to the queue executes the logic by calling the LLM service -> the LLM service calls Meta Llama 3.3 verastile model and published the response to another RabbitMQ queue and to the TTS RabbitMQ queue

5. The websocket handler for handling LLM response subscribed to that queue gets the LLM response from the worker and sends it to the Frontend -> The Frontend displays the response

6. The task sent to the TTS worker is handled by the TTS service and the response is published to the websocket handler which then displays the audio response from the LLM text

## Tech stack:

* **Django:** As the Backend Framework for defining the api endpoints for the REST server, configuring the REST server, Websocket server and the gRPC server for startup logic and graceful shutdown, setting variables for the RabbitMQ email worker to use and starting all three servers via the addition of uvicorn server

* **Whisper AI:** As the AI model for converting audio to text

* **Silero VAD:** As the AI model for speech detection based on the probability ensuring silence timeout and perfect speech detection

* **XTTS v2 encoder** As the Encoder for converting text to speech

* **Postgres:** Used as the DBMS for storing user credentials and token using the Django Database

* **Pgbouncer**: Used for connection pooling for live connections 

* **Next:** As the Frontend Framework for prompting the user to register or/and login with the mic audio streaming for sending the continious streams to the Backend

* **RabbitMQ:** Used as the Message Queue for sending email to the user after it registers, send ing the audio converted to speech to the worker handler subscibing to the queue and for delivering the LLM response to the web socket LLM listener and the TTS worker response to the same listener

* **Redis:** Used for rate limiting the API requests to the Backend

* **Docker:** Used for containerizing the Web Application and for starting and running the DB, Message Queue and API rate limiter containers

* **Kubernetes** Used for orchestration of Infra pods and the application pods

* **Helm** Used for packaging the application with resuable infra Helm Charts(Postgres, RabbitMQ, Redis)

## Guidelines for starting with the web app

* **Configuration:** Create the .env file and Configure the GROQ API key for model based on your generated API key
* **pre-requisites:**

  * ensure the python interpeter version 3.11 or above is installed
  * ensure Docker is installed on the machine
  * ensure kind and kubectl is installed
  * ensure Helm is installed

* **Build the Docker image:**

  ```bash
  docker build -t voice-ai-web .
  ```
  
* **Starting the Backend server:** to start the Backend server follow these commands:

  ```bash
  cd voiceAI 
  ```
  ```bash
  chmod +x start.sh
  ./start.sh
  ```

* **Starting the Frontend server:** start the Frontend server by following these commands:

  ```bash
  cd frontend
  bun run dev
  ```

* **Running the Docker Containers:** Access the Docker Compose file and run the services seperately for creating and running the          Postgres,          Redis and RabbitMQ container.

  If you want to use the containerized Backend instead of starting the Backend from the terminal just follow this command

  ```bash
  docker compose up -d
  ```

* **Running on Kind Cluster:** 

    ```bash
    cd kind
    chmod +x ./create-cluster.sh
    ./create-cluster.sh
    ```

* **Deploying with Helm:**
  ```bash
  cd voice-ai-chart
  helm upgrade --install voice-ai ./
