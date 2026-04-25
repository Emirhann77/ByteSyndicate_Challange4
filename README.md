# ByteSyndicate_Challange4

## Frontend (React)

The React demo UI lives in `frontend/`.

### Run locally

```bash
cd frontend
npm install
npm run dev
```

### FastAPI integration later

The app calls `createExperimentPlanClient().generatePlan()` in `frontend/src/lib/experimentPlanClient.ts`.
Replace the mock implementation with a `fetch()` call to your FastAPI endpoint and keep the UI unchanged.