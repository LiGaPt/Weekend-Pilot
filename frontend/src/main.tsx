import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ObservabilityPage } from "./observability/ObservabilityPage";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {window.location.pathname === "/observability" ? <ObservabilityPage /> : <App />}
  </React.StrictMode>,
);
