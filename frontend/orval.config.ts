import { defineConfig } from 'orval';

export default defineConfig({
  mewtwo: {
    input: {
      target: 'http://localhost:8000/openapi.json',
    },
    output: {
      mode: 'tags-split',
      target: './src/generated/api.ts',
      schemas: './src/generated/models',
      client: 'react-query',
      mock: true,
      prettier: true,
      override: {
        mutator: {
          path: './src/lib/axios-instance.ts',
          name: 'customInstance',
        },
        query: {
          useQuery: true,
          useMutation: true,
          signal: true,
          version: 5,
        },
      },
    },
    hooks: {
      afterAllFilesWrite: 'prettier --write',
    },
  },
});