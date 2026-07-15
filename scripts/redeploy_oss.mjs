import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import http from 'node:http'
import OSS from 'ali-oss'

const projectRoot = path.resolve(import.meta.dirname, '..')
const distDir = path.join(projectRoot, 'dist')

const region = 'oss-cn-shanghai'
const bucket = 'fund-system-bucket'
const accountId = '1238993556817547'

const accessKeyId = process.env.ALIBABA_CLOUD_ACCESS_KEY_ID || process.env.ALIYUN_ACCESS_KEY_ID
const accessKeySecret = process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET || process.env.ALIYUN_ACCESS_KEY_SECRET

if (!accessKeyId || !accessKeySecret) {
  console.error('Missing ALIBABA_CLOUD_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_SECRET')
  process.exit(1)
}

const client = new OSS({ region, accessKeyId, accessKeySecret, bucket })

const guessContentType = (key) => {
  const k = key.endsWith('.gz') ? key.slice(0, -3) : key
  if (k.endsWith('.html')) return 'text/html; charset=utf-8'
  if (k.endsWith('.js'))   return 'application/javascript; charset=utf-8'
  if (k.endsWith('.css'))  return 'text/css; charset=utf-8'
  if (k.endsWith('.json')) return 'application/json; charset=utf-8'
  if (k.endsWith('.svg'))  return 'image/svg+xml'
  if (k.endsWith('.png'))  return 'image/png'
  if (k.endsWith('.ico'))  return 'image/x-icon'
  if (k.endsWith('.map'))  return 'application/json; charset=utf-8'
  return 'application/octet-stream'
}

const guessCacheControl = (key) => {
  if (key === 'index.html') return 'no-cache'
  if (key.startsWith('assets/')) return 'public, max-age=31536000, immutable'
  return 'public, max-age=86400'
}

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

const setBucketPolicy = () => {
  return new Promise((resolve, reject) => {
    const policy = JSON.stringify({
      Version: '1',
      Statement: [{
        Effect: 'Allow',
        Principal: ['*'],
        Action: ['oss:GetObject'],
        Resource: [`acs:oss:*:${accountId}:${bucket}/*`]
      }]
    })

    const contentMD5 = crypto.createHash('md5').update(policy).digest('base64')
    const contentType = 'application/json'
    const date = new Date().toUTCString()

    const resource = `/${bucket}/?policy`
    const stringToSign = `PUT\n${contentMD5}\n${contentType}\n${date}\n${resource}`
    const signature = crypto.createHmac('sha1', accessKeySecret).update(stringToSign).digest('base64')
    const auth = `OSS ${accessKeyId}:${signature}`

    const options = {
      hostname: `${bucket}.${region}.aliyuncs.com`,
      path: '/?policy',
      method: 'PUT',
      headers: {
        'Content-Type': contentType,
        'Content-MD5': contentMD5,
        'Date': date,
        'Authorization': auth,
        'Content-Length': Buffer.byteLength(policy)
      }
    }

    const req = http.request(options, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        if (res.statusCode === 200) {
          console.log('Bucket policy set successfully')
          resolve()
        } else {
          console.warn(`Policy status: ${res.statusCode}, body: ${data}`)
          resolve() // non-fatal
        }
      })
    })
    req.on('error', reject)
    req.write(policy)
    req.end()
  })
}

const main = async () => {
  if (!fs.existsSync(distDir)) throw new Error(`dist not found: ${distDir}`)

  // 1. Set bucket policy
  await setBucketPolicy()

  // 2. Enable static website
  await client.putBucketWebsite(bucket, { index: 'index.html', error: 'index.html' })
  console.log('Static website configured')

  // 3. Set bucket ACL
  await client.putBucketACL(bucket, 'public-read')
  console.log('Bucket ACL set to public-read')

  // 4. Upload all files
  const files = listFiles(distDir)
  for (const absPath of files) {
    const rel = path.relative(distDir, absPath)
    const key = rel.split(path.sep).join('/')

    const headers = {
      'Content-Type': guessContentType(key),
      'Cache-Control': guessCacheControl(key),
      'x-oss-object-acl': 'public-read',
    }
    if (key.endsWith('.gz')) headers['Content-Encoding'] = 'gzip'

    console.log(`Uploading: ${key}`)
    await client.put(key, fs.createReadStream(absPath), { headers })
  }

  // 5. Set referral and CORS configurations
  try {
    await client.putBucketReferer(bucket, { allowEmpty: true })
    console.log('Referer config: allow empty')
  } catch(e) { console.warn('Referer config:', e.message) }

  try {
    await client.putBucketCors(bucket, [{
      allowedOrigin: '*',
      allowedMethod: ['GET', 'HEAD'],
      allowedHeader: ['*'],
      exposeHeader: ['Content-Length', 'Content-Type'],
      maxAgeSeconds: 3600
    }])
    console.log('CORS configured')
  } catch(e) { console.warn('CORS config:', e.message) }

  const websiteUrl = `http://${bucket}.${region}.aliyuncs.com/`
  console.log(`\nDeploy completed!`)
  console.log(`Website: ${websiteUrl}`)
  console.log(`Direct: https://${bucket}.${region}.aliyuncs.com/index.html`)
  console.log(`\nIMPORTANT: Direct HTTPS access may still force-download HTML files.`)
  console.log(`Use the HTTP Website URL above or configure a custom domain for best results.`)
}

main().catch((e) => {
  console.error(e?.message || e)
  process.exit(1)
})
