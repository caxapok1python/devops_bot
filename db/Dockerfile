FROM postgres
COPY init.sql /docker-entrypoint-initdb.d/
RUN apt-get update && apt-get install openssh-client openssh-server -y
RUN mkdir /oracle/ && mkdir /oracle/pg_data/ && mkdir /oracle/pg_data/archive/ && chown -R postgres:postgres /oracle
CMD ["postgres"]
