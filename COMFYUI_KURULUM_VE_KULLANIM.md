# Video Studyosu — Ücretsiz ComfyUI bağlantısı

Bu entegrasyon, ComfyUI'yi aynı bilgisayarda çalıştırır. Video Studyosu ComfyUI'nin yerel HTTP API'sine bağlanır; ücretli bulut API'si veya API anahtarı kullanmaz.

## 1. ComfyUI'yi kur

1. Resmî proje ve kurulum yönergeleri: https://github.com/Comfy-Org/ComfyUI
2. Bilgisayarındaki ekran kartına/işletim sistemine uygun resmî kurulum yolunu izle.
3. ComfyUI'yi başlat. Varsayılan yerel adres genellikle http://127.0.0.1:8188 olur.
4. ComfyUI içinde bir metinden görsele (text-to-image) iş akışı aç.
5. Gerekli checkpoint/model dosyasını ComfyUI'nin model klasörüne ayrıca kur. Model ağırlıkları ücretsiz indirilebilir olsa da lisansları modele göre değişir; ticari kullanım iznini ayrıca kontrol et.

## 2. API iş akışını dışa aktar

ComfyUI arayüzünde **File → Export Workflow (API)** seçeneğiyle API JSON dosyasını dışa aktar. Normal workflow JSON değil, API formatı kullanılmalıdır.

İş akışında standart düğümler bulunmalı:
- CLIPTextEncode (pozitif prompt)
- KSampler (seed)
- EmptyLatentImage (width/height)
- SaveImage

## 3. Video Studyosu'na bağlan

1. ComfyUI'yi açık bırak.
2. Video Studyosu sahne düzenleyicisini aç.
3. ComfyUI adresini `http://127.0.0.1:8188` olarak bırak.
4. **API iş akışı JSON seç** düğmesiyle dışa aktardığın JSON dosyasını seç.
5. Bir sahne seç ve **ComfyUI ile AI görsel üret** düğmesine bas.

Üretim arka planda yapılır; arayüz beklerken donmamalıdır. Tamamlanan görsel sahneye aktarılır ve proje görselleri klasörüne kaydedilir.

## Sorun giderme

- Bağlantı reddedildi: ComfyUI'nin çalıştığını ve adres/portun doğru olduğunu kontrol et.
- Node validation error: Eksik model, node veya hatalı API workflow olabilir. ComfyUI'de workflow'u önce elle çalıştırıp doğrula.
- SaveImage çıktısı yok: İş akışına SaveImage düğümü ekle.
- İlk üretim uzun sürebilir: Model ilk kez belleğe yükleniyor olabilir.
- VRAM/RAM yetersizliği: Daha küçük çözünürlük veya daha hafif model kullan.

## Ücret ve lisans

ComfyUI açık kaynaklıdır. Yerel kullanım için servis başına ücret yoktur. Model dosyalarının indirilmesi, disk alanı ve elektrik kullanımı gerekir. Her modelin lisansı farklı olabilir; ticari YouTube videolarında kullanmadan önce model lisansını kontrol et.

Kaynaklar:
- ComfyUI: https://github.com/Comfy-Org/ComfyUI
- API routes: https://docs.comfy.org/development/comfyui-server/comms_routes
- API workflow format: https://docs.comfy.org/development/api-development/workflow-api-format
