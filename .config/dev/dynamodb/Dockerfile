FROM amazon/dynamodb-local

USER root
RUN mkdir -p /home/dynamodblocal/data && \
    chown -R dynamodblocal:dynamodblocal /home/dynamodblocal/data
USER dynamodblocal
