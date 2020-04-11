FROM ubuntu:16.04

# More SSL cert problems on automatic build on Docker hub:
ENV GIT_SSL_NO_VERIFY true

ENV DEBIAN_FRONTEND noninteractive
ENV APTLIST="git libav-tools libffi-dev libopus-dev libssl-dev python3.7 unzip ffmpeg wget ca-certificates build-essential"

RUN apt-get update -y
RUN apt-get install -y --no-install-recommends software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get update
RUN apt-get install -y --no-install-recommends $APTLIST
RUN apt-get clean
RUN ln -s /usr/bin/python3.7 /usr/bin/python
# Keep getting certificate errors when Docker Hub is building this image - added -no-check-certificate
RUN wget --no-check-certificate -O /tmp/get-pip.py http://bootstrap.pypa.io/get-pip.py && python3.7 /tmp/get-pip.py

COPY . .

RUN pip install -r requirements.txt

CMD ["python", "src/lamorocha_bot.py"]