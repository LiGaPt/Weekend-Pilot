import React from "react";
import ReactDOM from "react-dom/client";
import { ObservabilityPage } from "./observability/ObservabilityPage";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ObservabilityPage />
  </React.StrictMode>,
);
