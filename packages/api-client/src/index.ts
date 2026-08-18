export * from "./generated";
// The one client instance every generated call goes through, so that the app
// can configure it once — the global fetch wrapper's whole reason to exist.
export { client } from "./generated/client.gen";
