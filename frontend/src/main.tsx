// Entry point: loads the fonts and global styles, then mounts the React app
// with its data loading (React Query) and page addresses (React Router).
// "standard.css" is the Bricolage Grotesque file that includes its width axis.
import "@fontsource-variable/bricolage-grotesque/standard.css";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist/wght-italic.css";
import "@fontsource-variable/geist-mono";
import "katex/dist/katex.min.css";
import "./design/tokens.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./App";

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
