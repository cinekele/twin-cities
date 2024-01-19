# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PROD_MODE 1

ENV USER=<wikidata_username>
ENV PASSWORD=<wikidata_password>

# Set the working directory in the container to /app
WORKDIR /app

COPY ./src /app
COPY requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


RUN mkdir -p /app/data

# Make port 8050 available to the world outside this container
EXPOSE 8050

# Scrape data and create graph, and run app.py when the container launches
CMD ["/bin/bash", "-c", "python scrape_to_graph.py && gunicorn -b 0.0.0.0:8050 app:server"]
