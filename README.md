# Voice-AI-Web-App

## General Flow of the Web App:

1. User registers -> User login -> DB store via postgres
   
2. User speaks to the browser mic -> Websocket listens and process the audio -> sends to Silero VAD evaluating the probability
   
3. Based on the threshold the audio buffer is passed to the gRPC servicer -> the servicer calls Whisper to Speech to Text Conversion -> The converted text is published to the RabbitMQ queue
   
4. The worker subscribed to the queue executes the logic by calling the LLM service -> the LLM service calls Meta Llama 3.3 verastile model and published the response to another RabbitMQ queue
   
5. The websocket handler for handling LLM response subscribed to that queue gets the LLM response from the worker and sends it to the Frontend -> The Frontend displays the response

## Tech stack:

* **Django:** As the Backend Framework for running both REST, Websocket and the gRPC server via the addition of uvicorn server
  
* **Whisper AI:** As the AI model for converting audio to text
  
* **Silero VAD:** As the AI model for speech detection based on the probability ensuring silence timeout and perfect speech detection
  
* **Postgres:** Used as the DBMS for storing user credentials and token using the Django Database
  
* **Next:** As the Frontend Framework for prompting the user to register or/and login with the mic audio streaming for sending the continious streams to the Backend
  
* **RabbitMQ:** Used as the Message Queue for sending email to the user after it registers, send ing the audio converted to speech to the worker handler subscibing to the queue and for delivering the LLM response to the web socket LLM listener
  
* **Redis:** Used for rate limiting the API requests to the Backend
  
* **Docker:** Used for containerzing the Web Application and for starting and running the DB, Message Queue and API rate limiter containers

## Guidelines for starting with the web app

* **Configuration:** Create the .env file and Configure the GROQ API key for model based on your generated API key

* **pre-requisites:**
     * ensure the python interpeter version 3.11 or above is installed
       
     * ensure Docker is installed on the machine
       

* **Starting the Backend server:** to start the Backend server follow these commands:
    ```bash
    cd voiceAI #from root
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

  * **Running the Docker Containers:** Access the Docker Compose file and run the services seperately for creating and running the           Postgres,          Redis and RabbitMQ container.

     If you want to use the containerized Backend instead of starting the Backend from the terminal just follow this command

     ```bash
     docker compose up -d
     ```

