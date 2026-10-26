FROM node:22-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --omit=dev && npm cache clean --force
COPY audio.mjs ./
COPY web ./web
RUN mkdir /data && chown node:node /data
USER node
ENV HOST=0.0.0.0 PORT=3000 DATA_DIR=/data
EXPOSE 3000
CMD ["node", "web/server.mjs"]
