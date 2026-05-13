FROM amazon/dynamodb-local:latest@sha256:d89f8fcc6b1a39cb35976c248ed42a28c66ae00dc043099210f5571e42648ab4

USER root
RUN mkdir -p /home/dynamodblocal/data && \
    chown -R dynamodblocal:dynamodblocal /home/dynamodblocal/data
USER dynamodblocal
