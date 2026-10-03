// Owned by the Engine track. Web Worker that runs transformers.js models.
// Offline notes:
// - Serve models from /models/ (env.localModelPath, env.allowRemoteModels = false).
// - Point env.backends.onnx.wasm.wasmPaths at a local copy of the ORT wasm files;
//   by default transformers.js fetches them from a CDN, which breaks airplane mode.
export {};
