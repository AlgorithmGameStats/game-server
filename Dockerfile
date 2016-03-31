#
# Game Server Dockerfile
#
# https://github.com/AlgorithmGameStats/game-server
#
FROM python:2.7
MAINTAINER itomaldonado <mo.maldonado@gmail.com>

# Create application folder and set it as working directory
RUN mkdir -p /opt/game-server
WORKDIR /opt/game-server

# Add application files
COPY requirements.txt ./
COPY schemas/ schemas/
COPY settings.py ./
COPY game-server.py ./

# Install all python packages
RUN pip install -r requirements.txt

# Expose port and add command
EXPOSE 5000
CMD ["python2", "-u", "game-server.py"]