# FacilityOps frontend — React/Vite SPA.
#
# IMPORTANT, FIXED BUG: Vite bakes VITE_* env vars into the JS bundle at
# BUILD time (`npm run build`), not at container-run time — the previous
# version of this Dockerfile had no ARG/ENV before the build step, so
# setting VITE_API_BASE_URL in docker-compose's `environment:` block did
# nothing (the frontend service's env var was never seen by `npm run
# build`, only by the already-built `serve` process afterwards, which
# doesn't read it). It happened to still work for local docker-compose
# only because energyService.js's hardcoded fallback
# ('http://localhost:8000/api') coincidentally matches. It would silently
# break for any real deployment where the backend isn't on localhost. Fixed
# by declaring it as a build ARG and exporting it as an ENV before `npm
# run build` runs, and docker-compose.yml now passes it as a `build.args:`,
# not a runtime `environment:`.
FROM node:24-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM node:24-slim
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist
EXPOSE 5173

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://localhost:5173').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["serve", "-s", "dist", "-l", "5173"]
