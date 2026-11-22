# Video Studyosu — Yeni Arayüz ve Kullanıcı Akışı

Bu belge, Video Studyosu'nun bir sonraki arayüz düzenlemesi için kabul edilen ürün gereksinimlerini tanımlar. Mevcut uygulamanın işlevleri korunacak; bu belge tek başına özelliklerin uygulandığı anlamına gelmez.

## Ana sekmeler

1. **Video Oluştur**
2. **Senarist** — Video Oluştur'dan ayrı, kendi sekmesi olacak. Senaryo hazırlama ve düzenleme burada yapılacak.
3. **Eski Videoyu Düzenle** — Daha önce oluşturulmuş videoları yeniden işlemek için ayrı sekme.
4. **Güncelleme** — Programın kendi içinden GitHub sürümünü kontrol edip güncelleme yapacağı bölüm. Ayrı bir güncelleme programı kurulmayacak.

## 1. Video Oluştur: adım adım sihirbaz

Kullanıcı önce **Video Yapalım** düğmesine basar. Sonrasında tek ekranda bütün ayarlar gösterilmez; her adımda bir pencere/sayfa açılır. Kullanıcı seçimini yaptıktan sonra sonraki adıma geçer. Önceki adıma dönüp seçimlerini değiştirebilir.

### Adım 1 — Hangi platform / video türü?

Seçenekler:
- YouTube yatay video
- YouTube Shorts
- Instagram Reels
- Instagram Hikâye
- TikTok
- Benzer dikey/kısa video platformları
- Özel ölçü / özel format (uygunsa)

Seçilen platforma göre en-boy oranı, çözünürlük ve önerilen video süresi ayarlanır. Platform kuralları uygulamada güncel ve doğrulanmış değerlerle tutulmalı; doğrulanmamış süre sınırları sabit kabul edilmemeli.

### Adım 2 — Karakterler

Kullanıcı videoda yer alacak karakterleri seçer veya oluşturur:
- Yeni karakter oluştur
- Yeni karakteri kaydet ve ileride tekrar kullan
- Kayıtlı/eski karakterlerimden seç
- Videoda karakter kullanma

Karakter kartında ad, görsel/referans, kısa tanım ve gerekli tutarlılık notları bulunabilir. Kullanıcı bir karakteri kaydettiğinde sonraki projelerde tekrar seçebilmelidir. Kayıtlı karakterin görünümü ve temel özellikleri yeni sahnelerde mümkün olduğunca tutarlı korunmalıdır.

### Adım 3 — Ses sistemi

Ses tercihleri ayrı bir adımda sorulur:
- Anlatıcı sesi / konuşmacı
- Erkek veya kadın ses seçenekleri (mevcut TTS sağlayıcısının sunduklarıyla sınırlı)
- Ses tarzı ve konuşma hızı
- Karakter konuşmaları mı, dış ses mi, sessiz video mu?
- Gerekirse sahne/karakter bazında ses seçimi

Arayüz, gerçekten desteklenmeyen ses özelliklerini varmış gibi göstermemeli.

### Adım 4 — Altyazı

Kullanıcı altyazı tercihini seçer:
- Altyazı olsun / olmasın
- Altyazı dili (Türkçe, İngilizce ve uygulamanın gerçekten desteklediği diğer diller)
- Gerekirse kaynak konuşma dili ve çeviri dili
- Altyazı görünümü için temel tercihler

### Adım 5 — Senaryo

- Senaryo metni kullanıcıdan alınır veya Senarist sekmesinde hazırlanmış/onaylanmış senaryo buraya aktarılır.
- Senaryo henüz yoksa kullanıcı Senarist sekmesine yönlendirilebilir.
- Senaryo onaylanmadan sahne üretimine geçilmez.

### Adım 6 — Sahneler

- Senaryo sahnelere ayrılır.
- Her sahnenin metni, karakterleri, görsel açıklaması ve ses/konuşma içeriği gösterilir.
- Kullanıcı sahne ekleyebilir, silebilir, sıralayabilir ve düzenleyebilir.

### Adım 7 — Ön izleme

- Sahne görselleri ve varsa ses/altyazı ön izlemesi gösterilir.
- Kullanıcı sahne bazında değişiklik isteyebilir.
- **Şurayı düzelt / Bu sahneyi değiştir** gibi bir düzenleme alanı bulunur.
- Değişiklikler uygulanmadan önce veya sonra karşılaştırmalı ön izleme sunulması tercih edilir.

### Adım 8 — Video oluştur

Kullanıcı son onayı verdikten sonra video oluşturulur. İşlem durumu ve ilerleme gösterilir. Hata olursa anlaşılır hata mesajı ve yeniden deneme seçeneği sunulur.

### Adım 9 — Oluşturulan videoyu izle

- Tamamlanan video uygulama içinde oynatılır.
- Kaydetme konumu ve dosya adı gösterilir.
- Yeniden oluşturma veya Eski Videoyu Düzenle sekmesine gönderme seçenekleri sunulur.

## 2. Eski Videoyu Düzenle sekmesi

Bu sekme, daha önce oluşturulmuş videoları yeniden kullanmaya yönelik olacak:
- Mevcut videoyu aç / içe aktar
- Altyazıyı kaldır, yeniden oluştur veya dilini değiştir
- Platformu değiştir (ör. yatay YouTube videosunu dikey kısa video formatına uyarlama)
- En-boy oranını ve çıktı ölçülerini değiştir
- Uygun olduğunda sahne kırpma / kadrajı yeniden ayarlama
- Ses seviyesini veya desteklenen ses seçeneklerini düzenleme
- Yeni dosya olarak dışa aktar; orijinal videoyu varsayılan olarak ezme

Platform değişikliği yalnızca dosyanın boyutunu değiştirmek değildir; kadraj, altyazı yerleşimi ve sahne kompozisyonu da yeni formata göre gözden geçirilmelidir.

## 3. Senarist sekmesi

Senarist, Video Oluştur sihirbazının içinde kaybolan bir alt adım değil, ana arayüzde ayrı bir sekme olacak. Burada fikirden senaryoya, senaryodan sahnelere hazırlık yapılacak. Onaylanan senaryo Video Oluştur akışına aktarılabilecek.

## 4. Güncelleme sekmesi

- Mevcut Video Studyosu'nun içinde bulunacak.
- Kullanıcı güncelleme kontrolünü ve kurulumu programın içinden başlatacak.
- Ayrı bir güncelleme uygulaması kullanıcıya kurdurulmayacak.
- Projeler, kayıtlı karakterler, ayarlar ve oluşturulmuş videolar güncelleme sırasında korunacak.
- Güncelleme öncesi mevcut uygulama dosyası yedeklenecek; güncelleme başarısız olursa geri dönüş yolu bulunacak.

## Tasarım ilkeleri

- Kullanıcıyı bir anda çok sayıda ayarla boğma; adım adım ilerlet.
- Her adımda **Geri**, **Devam** ve uygun yerde **Atla** seçenekleri olsun.
- Seçimler proje dosyasına kaydedilsin; program kapanıp açıldığında kaldığı yerden devam edilebilsin.
- Platform, karakter, ses, altyazı ve senaryo seçimleri video projesinin parçası olarak saklansın.
- Mevcut çalışan özellikleri yeni arayüze taşırken kaybetme.
- Arayüzde görünen her seçenek gerçekten çalışan bir işleve bağlı olsun; henüz desteklenmeyenler açıkça belirtilsin.
- Kullanıcının videoları, projeleri ve kayıtlı karakterleri uygulama güncellemelerinden bağımsız, kalıcı veri klasörlerinde saklansın.

## Uygulama sırası

1. Mevcut programın doğru kaynak sürümünü GitHub'a aktar ve ilk Windows derlemesini doğrula.
2. Mevcut uygulamanın içinde Güncelleme bölümünü tamamla ve gerçek güncelleme testini yap.
3. Ana arayüzü bu belgede tanımlanan sekmelere göre yeniden düzenle.
4. Video Oluştur sihirbazını platform → karakter → ses → altyazı → senaryo → sahneler → ön izleme → oluşturma → oynatma sırasıyla uygula.
5. Eski Videoyu Düzenle ve Senarist sekmelerini bağla.
6. Proje/karakter verilerinin güncelleme sonrasında korunduğunu test et.
