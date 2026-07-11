import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import OSS from 'ali-oss'

const projectRoot = path.resolve(import.meta.dirname, '..')
const distDir = path.join(projectRoot, 'frontend', 'dist')

const region = process.env.OSS_REGION || 'oss-cn-shanghai'
const bucket = process.env.OSS_BUCKET || 'fund-system-bucket'
const accessAlias = process.env.S_ACCESS_ALIAS || 'default'

const listFiles = (dir) => {
  const out = []
  const stack = [dir]
  while (stack.length) {
    const cur = stack.pop()
    const entries = fs.readdirSync(cur, { withFileTypes: true })
    for (const e of entries) {
      if (e.name === '.DS_Store') continue
      const p = path.join(cur, e.name)
      if (e.isDirectory()) stack.push(p)
      else if (e.isFile()) out.push(p)
    }
  }
  return out.sort()
}

const parseSAccessYaml = (yamlText, alias) => {
  const lines = yamlText.split(/\r?\n/)
  const startIdx = lines.findIndex((l) => l.trim() === `${alias}:`)
  if (startIdx === -1) throw new Error(`access alias not found: ${alias}`)

  const block = []
  for (let i = startIdx + 1; i < lines.length; i += 1) {
    const l = lines[i]
    if (!l.trim()) continue
    if (!/^\s+/.test(l)) break
    block.push(l.replace(/^\s+/, ''))
  }

  const kv = {}
  for (const l of block) {
    const m = l.match(/^([^:#]+):\s*(.+?)\s*$/)
    if (!m) continue
    const k = m[1].trim()
    let v = m[2].trim()
    v = v.replace(/^['"]/, '').replace(/['"]$/, '')
    const envRef = v.match(/^\$\{env\.([A-Z0-9_]+)\}$/)
    if (envRef) v = process.env[envRef[1]] || ''
    kv[k] = v
  }

  const accessKeyId = kv.AccessKeyID || kv.AccessKeyId || kv.accessKeyId || kv.accessKeyID
  const accessKeySecret = kv.AccessKeySecret || kv.accessKeySecret
  const securityToken = kv.SecurityToken || kv.securityToken
  const accountId = kv.AccountID || kv.accountId

  if (!accessKeyId || !accessKeySecret) throw new Error(`invalid access config for alias: ${alias}`)

  return { accessKeyId, accessKeySecret, securityToken, accountId }
}

const guessContentType = (key) => {
  const k = key.endsWith('.gz') ? key.slice(0, -3) : key
  if (k.endsWith('.html')) return 'text/html; charset=utf-8'
  if (k.endsWith('.js')) return 'application/javascript; charset=utf-8'
  if (k.endsWith('.css')) return 'text/css; charset=utf-8'
  if (k.endsWith('.json')) return 'application/json; charset=utf-8'
  if (k.endsWith('.svg')) return 'image/svg+xml'
  if (k.endsWith('.png')) return 'image/png'
  if (k.endsWith('.jpg') || k.endsWith('.jpeg')) return 'image/jpeg'
  if (k.endsWith('.ico')) return 'image/x-icon'
  if (k.endsWith('.map')) return 'application/json; charset=utf-8'
  return 'application/octet-stream'
}

const guessCacheControl = (key) => {
  if (key === 'index.html') return 'no-cache'
  if (key.startsWith('assets/')) return 'public, max-age=31536000, immutable'
  return 'public, max-age=86400'
}

const main = async () => {
  if (!fs.existsSync(distDir)) throw new Error(`dist not found: ${distDir}`)

  let accessKeyId = process.env.ALIBABA_CLOUD_ACCESS_KEY_ID || ''
  let accessKeySecret = process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET || ''
  let securityToken = process.env.ALIBABA_CLOUD_SECURITY_TOKEN || ''

  if (!accessKeyId || !accessKeySecret) {
    const sAccessPath = path.join(os.homedir(), '.s', 'access.yaml')
    const yamlText = fs.readFileSync(sAccessPath, 'utf8')
    const parsed = parseSAccessYaml(yamlText, accessAlias)
    accessKeyId = parsed.accessKeyId
    accessKeySecret = parsed.accessKeySecret
    securityToken = parsed.securityToken || ''
  }

  const client = new OSS({
    region,
    accessKeyId,
    accessKeySecret,
    stsToken: securityToken || undefined,
    bucket
  })

  await client.putBucketACL(bucket, 'public-read')
  await client.putBucketWebsite(bucket, {
    index: 'index.html',
    error: 'index.html'
  })

  const files = listFiles(distDir)
  for (const absPath of files) {
    const rel = path.relative(distDir, absPath)
    const key = rel.split(path.sep).join('/')

    const headers = {
      'Content-Type': guessContentType(key),
      'Cache-Control': guessCacheControl(key)
    }
    if (key.endsWith('.gz')) headers['Content-Encoding'] = 'gzip'

    await client.putStream(key, fs.createReadStream(absPath), { headers })
  }

  const endpoint = `https://${bucket}.${region}.aliyuncs.com/`
  const objectEndpoint = `https://${bucket}.${region}.aliyuncs.com/index.html`
  process.stdout.write(`DEPLOY_OK\n${endpoint}\n${objectEndpoint}\n`)
}

main().catch((e) => {
  process.stderr.write(`${e?.message || e}\n`)
  process.exitCode = 1
})
