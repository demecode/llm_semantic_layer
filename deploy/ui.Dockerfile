FROM node:20-alpine

WORKDIR /app

COPY ui/package*.json /app/
RUN npm ci

COPY ui /app

ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "-p", "3000", "-H", "0.0.0.0"]