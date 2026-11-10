FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY firm_lab ./firm_lab
RUN pip install --no-cache-dir .
RUN useradd -m lab && mkdir /data && chown lab:lab /data
USER lab
ENV FIRM_LAB_DATA=/data
EXPOSE 8810
CMD ["firm-lab","serve","--host","0.0.0.0","--port","8810","--data","/data"]
