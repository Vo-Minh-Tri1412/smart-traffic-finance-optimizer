import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import CompareView from "./views/CompareView";
import DistrictView from "./views/DistrictView";
import FinanceView from "./views/FinanceView";
import OverviewView from "./views/OverviewView";
import ReplayView from "./views/ReplayView";
import RunsView from "./views/RunsView";
import SystemView from "./views/SystemView";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OverviewView />} />
        <Route path="district" element={<DistrictView />} />
        <Route path="runs" element={<RunsView />} />
        <Route path="replay" element={<ReplayView />} />
        <Route path="replay/:runId" element={<ReplayView />} />
        <Route path="compare" element={<CompareView />} />
        <Route path="finance" element={<FinanceView />} />
        <Route path="system" element={<SystemView />} />
      </Route>
    </Routes>
  );
}
