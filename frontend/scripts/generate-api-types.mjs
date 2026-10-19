import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendDir = resolve(__dirname, '..');
const projectRoot = resolve(frontendDir, '..');
const backendScript = resolve(projectRoot, 'backend', 'scripts', 'generate_schema.py');
const openapiJson = resolve(frontendDir, 'openapi.json');
const outputFile = resolve(frontendDir, 'src', 'api', 'generated.ts');

try {
  if (existsSync(backendScript)) {
    console.log('[generate-api-types] Generating OpenAPI schema from backend...');
    execSync(`python "${backendScript}"`, {
      cwd: projectRoot,
      stdio: 'pipe',
      encoding: 'utf-8',
    });
  } else {
    console.warn('[generate-api-types] Backend script not found, using existing openapi.json if available');
  }

  if (!existsSync(openapiJson)) {
    console.error('[generate-api-types] No openapi.json found; refusing to write placeholder types.');
    process.exit(1);
  }

  console.log('[generate-api-types] Generating TypeScript types from OpenAPI schema...');

  execSync(`npx openapi-typescript openapi.json -o src/api/generated.ts`, {
    cwd: frontendDir,
    stdio: 'pipe',
    encoding: 'utf-8',
  });

  console.log(`[generate-api-types] Types generated at: ${outputFile}`);
} catch (err) {
  // 不再写 placeholder 并 exit 0：那会让类型安全静默退化为 never，CI 也发现不了。
  console.error('[generate-api-types] Failed to generate types:', err.message);
  process.exit(1);
}