import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import OSS from 'ali-oss'

const PROJECT_ROOT = path.resolve(new URL('.', import.meta.url).pathname, '..')
const DEFAULT_DIST_DIR = path.join(PROJECT_ROOT, 'frontend', 'dist')
const DEFAULT_BUCKET = 'fund-system-bucket'
const DEFAULT_REGION = 'oss-cn-shanghai'

const CONTENT_TYPE_BY_EXT = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.map': 'application/json; charset=utf-8'
}

function parseArgs(argv) {
  const args = {}
  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i]
    if (!item.startsWith('--')) {
      continue
    }
    const key = item.slice(2)
    const next = argv[i + 1]
    if (next && !next.startsWith('--')) {
      args[key] = next
      i += 1
      continue
    }
    args[key] = true
  }
  return args
}

async function listFilesRecursively(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      const nested = await listFilesRecursively(fullPath)
      files.push(...nested)
      continue
    }
    if (entry.isFile()) {
      files.push(fullPath)
    }
  }
  return files
}

function guessContentType(filePath) {
  const ext = path.extname(filePath).toLowerCase()
  return CONTENT_TYPE_BY_EXT[ext] || 'application/octet-stream'
}

async function tryLoadKeysFromSYaml() {
  const sYamlPath = path.join(PROJECT_ROOT, 's.yaml')
  let content = ''
  try {
    content = await fs.readFile(sYamlPath, 'utf-8')
  } catch {
    return null
  }
  const idMatch = content.match(/^\s*ALIYUN_ACCESS_KEY_ID:\s*([^\s#]+)\s*$/m)
  const secretMatch = content.match(/^\s*ALIYUN_ACCESS_KEY_SECRET:\s*([^\s#]+)\s*$/m)
  if (!idMatch || !secretMatch) {
    return null
  }
  return { accessKeyId: idMatch[1], accessKeySecret: secretMatch[1] }
}

async function resolveCredentials() {
  const accessKeyId = process.env.ALIYUN_ACCESS_KEY_ID || process.env.ALIBABA_CLOUD_ACCESS_KEY_ID || ''
  const accessKeySecret = process.env.ALIYUN_ACCESS_KEY_SECRET || process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET || ''
  if (accessKeyId && accessKeySecret) {
    return { accessKeyId, accessKeySecret }
  }
  const fromYaml = await tryLoadKeysFromSYaml()
  if (fromYaml) {
    return fromYaml
  }
  throw new Error('缺少 OSS 凭证：请设置环境变量 ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET（或在 s.yaml 中提供）')
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const distDir = path.resolve(args.dist || process.env.FRONTEND_DIST_DIR || DEFAULT_DIST_DIR)
  const bucket = String(args.bucket || process.env.OSS_BUCKET || DEFAULT_BUCKET)
  const region = String(args.region || process.env.OSS_REGION || DEFAULT_REGION)
  const prefix = String(args.prefix || process.env.OSS_PREFIX || '').replace(/^\/+/, '').replace(/\/+$/, '')
  const dryRun = args['dry-run'] === true || String(process.env.DRY_RUN || '').toLowerCase() === 'true'

  const stat = await fs.stat(distDir).catch(() => null)
  if (!stat || !stat.isDirectory()) {
    throw new Error(`dist 目录不存在: ${distDir}，请先在 frontend/ 执行 npm run build`)
  }

  const { accessKeyId, accessKeySecret } = await resolveCredentials()
  const client = new OSS({
    region,
    bucket,
    accessKeyId,
    accessKeySecret
  })

  const files = await listFilesRecursively(distDir)
  files.sort()

  for (const filePath of files) {
    const rel = path.relative(distDir, filePath).split(path.sep).join('/')
    const objectKey = prefix ? `${prefix}/${rel}` : rel
    const contentType = guessContentType(filePath)
    const headers = { 'Content-Type': contentType }
    if (contentType.startsWith('text/html')) {
      headers['Content-Disposition'] = 'inline'
    }
    if (dryRun) {
      process.stdout.write(`[DRY_RUN] upload ${filePath} -> oss://${bucket}/${objectKey}\n`)
      continue
    }
    await client.put(objectKey, filePath, { headers })
    process.stdout.write(`uploaded oss://${bucket}/${objectKey}\n`)
  }
}

main().catch((err) => {
  process.stderr.write(`${err?.message || String(err)}\n`)
  process.exitCode = 1
})
