import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./styles.css";
import { AppProvider, useApp } from "./lib/ctx";
import { Layout } from "./components/ui";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import LiveMonitor from "./pages/LiveMonitor";
import ProfilDepth from "./pages/ProfilDepth";
import RiwayatEvent from "./pages/RiwayatEvent";
import DataUpload from "./pages/DataUpload";
import FormasiFG from "./pages/FormasiFG";
import ModelML from "./pages/ModelML";
import AnalisisAnomali from "./pages/AnalisisAnomali";
import Laporan from "./pages/Laporan";
import Pengaturan from "./pages/Pengaturan";

function Guard() {
  const { user } = useApp();
  if (!user) return <Navigate to="/login" replace />;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/monitor" element={<LiveMonitor />} />
        <Route path="/profil" element={<ProfilDepth />} />
        <Route path="/event" element={<RiwayatEvent />} />
        <Route path="/data" element={<DataUpload />} />
        <Route path="/formasi" element={<FormasiFG />} />
        <Route path="/model" element={<ModelML />} />
        <Route path="/anomali" element={<AnalisisAnomali />} />
        <Route path="/laporan" element={<Laporan />} />
        <Route path="/pengaturan" element={<Pengaturan />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<Guard />} />
        </Routes>
      </AppProvider>
    </BrowserRouter>
  </StrictMode>,
);
