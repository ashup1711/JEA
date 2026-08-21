import { tool } from "@opencode-ai/plugin"
import { randomUUID } from "crypto"
import fs from "fs"
import path from "path"

const LOGS_DIR = path.join(process.env.HOME || "~", ".opencode", "pipeline-logs")

function ensureDir() {
  fs.mkdirSync(LOGS_DIR, { recursive: true })
}

export const createRequestId = tool({
  description: "Generate a new unique pipeline request ID and initialize its log file",
  args: {},
  async execute() {
    ensureDir()
    const id = `req-${randomUUID().slice(0, 8)}`
    const logPath = path.join(LOGS_DIR, `${id}.jsonl`)
    fs.writeFileSync(
      logPath,
      JSON.stringify({
        event: "pipeline_start",
        request_id: id,
        timestamp: new Date().toISOString(),
      }) + "\n"
    )
    return id
  },
})

export const logEntry = tool({
  description: "Append a structured log entry for a pipeline request",
  args: {
    request_id: tool.schema.string().describe("The pipeline request ID"),
    agent: tool.schema.string().describe("Agent name"),
    phase: tool
      .schema.string()
      .describe("Phase: research|prompt|expert|qa"),
    attempt: tool.schema.number().describe("Attempt number (1-indexed)"),
    content: tool
      .schema.string()
      .describe("Prompt, summary, or report content"),
  },
  async execute(args) {
    ensureDir()
    const logPath = path.join(LOGS_DIR, `${args.request_id}.jsonl`)
    fs.appendFileSync(
      logPath,
      JSON.stringify({
        ...args,
        timestamp: new Date().toISOString(),
      }) + "\n"
    )
    return `Logged ${args.phase} entry for ${args.agent} (attempt ${args.attempt})`
  },
})

export const finalizeRequest = tool({
  description: "Mark a pipeline request as complete and return summary",
  args: {
    request_id: tool.schema.string().describe("The pipeline request ID"),
    status: tool.schema.string().describe("SUCCESS or FAILED"),
    summary: tool.schema.string().describe("Final summary of what was done"),
  },
  async execute(args) {
    ensureDir()
    const logPath = path.join(LOGS_DIR, `${args.request_id}.jsonl`)
    fs.appendFileSync(
      logPath,
      JSON.stringify({
        event: "pipeline_end",
        status: args.status,
        summary: args.summary,
        timestamp: new Date().toISOString(),
      }) + "\n"
    )
    const lines = fs.readFileSync(logPath, "utf-8").trim().split("\n").length
    return `Pipeline ${args.request_id}: ${args.status}. ${lines} log entries. Path: ${logPath}`
  },
})
