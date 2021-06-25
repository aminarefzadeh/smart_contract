from ubuntu:18.04

RUN apt-get update && \
    apt-get install -y software-properties-common

RUN add-apt-repository ppa:ethereum/ethereum && \
    apt-get update && \
    apt-get install -y solc

RUN apt-get install -y python3 python3-pip

ADD requirements.txt /usr/manticore/
RUN pip3 install -r /usr/manticore/requirements.txt

ADD . /usr/manticore
WORKDIR /usr/manticore
