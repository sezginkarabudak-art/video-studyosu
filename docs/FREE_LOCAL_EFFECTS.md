# Ücretsiz yerel görsel efektleri

Video Studyosu 5.6.2 ile gelen efektler FFmpeg'in açık kaynak filtrelerini kullanır. Ek API, abonelik veya bulut yüklemesi gerekmez.

## Yerleşik efektler
- Kapalı
- Sinematik: kontrast, renk dengesi, vignette ve hafif film gren
- Korku: daha yüksek kontrast, soğuk ton, vignette ve gren
- Vintage: sıcak renk dengesi ve film gren
- Siyah-beyaz
- Rüya: yumuşak odak ve hafif parlaklık
- Keskin ve canlı: keskinleştirme ve doygunluk

Efekt seçimi proje dosyasına kaydedilir ve yeni video oluşturulurken uygulanır. FFmpeg destekli filtrelerin kullanılabilirliği, uygulamayla gelen FFmpeg derlemesine bağlıdır.

## İncelenen ücretsiz yardımcı projeler
- FrameShift: https://github.com/gaurox/FrameShift — yerel görüntü/video iyileştirme ve RIFE kare arası üretimi. Ayrı bir uygulama; bu sürümde kodu veya modelleri içe aktarılmadı.
- ALH Pro: https://github.com/AlLHHH/ALH-Pro — yerel görüntü/video büyütme, kare arası üretimi, arka plan kaldırma ve ses temizleme. Ayrı uygulama; henüz entegrasyon yapılmadı.
- LocalSR: https://github.com/HerRei/local-upscale — yerel AI görüntü/video iyileştirme. Beta ve ağır model indirmeleri gerektirebilir.

Bu projelerden kod kopyalanmadı. Entegrasyon için ayrı lisans, model boyutu, donanım ve Windows paket uyumluluğu denetimi gerekir.
