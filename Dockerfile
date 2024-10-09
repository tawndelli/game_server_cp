FROM python:3-alpine
 
# Create app directory
WORKDIR /app
 
# Install app dependencies
COPY requirements.txt ./
 
RUN pip install -r requirements.txt
 
# Bundle app source
COPY . .

EXPOSE 8080
CMD [ "uvicorn", "game_server:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "8080" ]