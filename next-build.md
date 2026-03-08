ami github use kore action er maddhobe .exe file banai but issue hocche amar ek ek company er jonno funcitonal api change korte hoy jeta jhamela , cpanel/laravel diye ki emon kisu kora jay je ami request pathale git hub e oi url change hoye action hoye download hobe ? user just bujhbe je laravel theke download hocche



Route::post('/build-exe', [BuildController::class, 'buildExe']);

use Illuminate\Support\Facades\Http;

public function buildExe(Request $request)
{
    $companyApi = $request->input('company_api'); // user selected api

    $response = Http::withToken(env('GITHUB_TOKEN'))
        ->post("https://api.github.com/repos/USERNAME/REPO/actions/workflows/build.yml/dispatches", [
            'ref' => 'main', // main branch
            'inputs' => [
                'api_url' => $companyApi
            ]
        ]);

    if ($response->successful()) {
        return response()->json(['message' => 'Build triggered!']);
    } else {
        return response()->json(['error' => 'Failed to trigger build'], 500);
    }
}

$artifactZip = Http::withToken(env('GITHUB_TOKEN'))
    ->get("https://api.github.com/repos/USERNAME/REPO/actions/artifacts/ARTIFACT_ID/zip");

Storage::put('exe/company1.exe', $artifactZip->body());

Route::get('/download/{company}.exe', function($company){
    $path = storage_path("app/exe/{$company}.exe");
    return response()->download($path);
});


name: Build EXE

on:
  workflow_dispatch:
    inputs:
      api_url:
        description: 'Company API'
        required: true

jobs:
  build:
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup environment
        run: |
          echo "API_URL=${{ github.event.inputs.api_url }}" > .env

      - name: Build EXE
        run: |
          # Example: build using some script
          ./build_script.bat

      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: exe
          path: ./dist/myapp.exe