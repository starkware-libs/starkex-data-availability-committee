FROM ciimage/python:3.7

RUN apt update
RUN apt -y -o Dpkg::Options::="--force-overwrite" install python3.7-dev
RUN apt install -y make libgmp3-dev python3-pip python3.7-venv
# Installing cmake via apt doesn't bring the most up-to-date version.
RUN pip install cmake==3.22

COPY . /app/

# Build.
WORKDIR /app/
RUN ./build.sh

WORKDIR /app/

CMD ["/app/build/Release/src/starkware/committee/starkex_committee_exe"]

EXPOSE 8000