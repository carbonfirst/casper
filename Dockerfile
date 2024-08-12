FROM ghcr.io/kiwix/kiwix-tools:latest

# # set variables
# ENV PATH /local/bin:$PATH
# ENV DATA /data

RUN apk update
RUN apk add --no-cache bash
RUN apk add --no-cache shadow
RUN apk add --no-cache curl

RUN groupadd --gid 1002 casper && useradd -g root casper
USER root
# add non-root user
# RUN groupadd docker \
# && useradd -g docker docker
# Set the working directory to /data
WORKDIR /data
# # change owner
RUN chown -R root:root /data

EXPOSE 8080

# Copy the local directory to the container
COPY ./zim /data
ENTRYPOINT ["/usr/local/bin/kiwix-serve", "--port=8080", "--library", "/data/library.xml"]