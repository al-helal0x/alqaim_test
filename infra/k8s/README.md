# infra/k8s — مهمة #1 (K8s Manifests فعلية)

Manifests فعلية لنشر الخدمات الثلاث (`core-api`, `ai-platform`, `web`) على أي
كلستر Kubernetes محلي (kind/minikube) أو سحابي لاحقاً. كل خدمة لها:
`Deployment` + `Service` + `ConfigMap` + `Secret`، داخل namespace واحد `alqaim`.

> ملاحظة نطاق: هذه المهمة (#1) تغطي فقط الخدمات الثلاث القابلة للنشر من
> `infra/docker/*`. قاعدة البيانات (Postgres) و Redis و MinIO **ليست** ضمن
> هذه المهمة — فحوصات `/health` الحالية في core-api/ai-platform لا تتحقق من
> اتصال قاعدة البيانات أو Redis عند الإقلاع (راجع `main.py` في كل خدمة)، لذا
> تمرّ الفحوصات حتى بدون نشر تلك التبعيات في نفس الكلستر. لتشغيل السيناريوهات
> الوظيفية الفعلية (وليس فقط `/health`) يلزم نشرها لاحقاً — خارج حدود هذه
> المهمة، ويمكن أن تكون جزءاً من مهمة تجهيز المرحلة 2.

## البنية

```
infra/k8s/
├── namespace.yaml
├── kustomization.yaml
├── core-api/      {configmap,secret,deployment,service}.yaml
├── ai-platform/    {configmap,secret,deployment,service}.yaml
└── web/           {configmap,secret,deployment,service}.yaml
```

## 1) بناء الصور محلياً

من جذر المستودع:

```bash
docker build -f infra/docker/Dockerfile.core-api   -t alqaim/core-api:local   .
docker build -f infra/docker/Dockerfile.ai-platform -t alqaim/ai-platform:local .
docker build -f infra/docker/Dockerfile.web         -t alqaim/web:local        .
```

## 2) تحميل الصور إلى الكلستر المحلي

مع `kind`:

```bash
kind load docker-image alqaim/core-api:local
kind load docker-image alqaim/ai-platform:local
kind load docker-image alqaim/web:local
```

مع `minikube`:

```bash
minikube image load alqaim/core-api:local
minikube image load alqaim/ai-platform:local
minikube image load alqaim/web:local
```

(الـ Manifests تستخدم `imagePullPolicy: IfNotPresent` تحديداً لتفادي محاولة
سحب الصور من registry خارجي غير موجود بعد.)

## 3) التطبيق على الكلستر

```bash
kubectl apply -k infra/k8s/
```

## 4) التحقق

```bash
kubectl -n alqaim get pods -w
kubectl -n alqaim port-forward svc/core-api 8000:8000 &
curl -sf http://localhost:8000/health && echo OK

kubectl -n alqaim port-forward svc/ai-platform 8100:8100 &
curl -sf http://localhost:8100/health && echo OK

kubectl -n alqaim port-forward svc/web 3000:3000 &
curl -sf http://localhost:3000/ && echo OK   # لا يوجد /health مخصص بعد لـ web
```

توقّع الحالة `Running` و`READY 1/1` لكل الـ Pods الثلاثة خلال ثوانٍ من
الإقلاع (لا تبعيات قاعدة بيانات مطلوبة لنجاح `/health` نفسه — راجع الملاحظة
أعلاه).

## فجوة موثَّقة (خارج نطاق هذه المهمة)

`apps/web` لا يملك مساراً مخصصاً `/health` (Next.js App Router). استُخدم "/"
مؤقتاً في `readinessProbe`/`livenessProbe` لأنه يرد 200 فور اكتمال الإقلاع.
مقترح لمهمة منفصلة صغيرة: إضافة
`apps/web/src/app/api/health/route.ts` يرجع `{status: "ok"}`، ثم تحديث
`web/deployment.yaml` هنا من `/` إلى `/api/health` (تعديل سطرين فقط).

كذلك: `ALQAIM_NEXT_PUBLIC_API_URL` — انظر التعليق في `web/configmap.yaml`؛
هذا المتغير يُطبَخ وقت `docker build` لا وقت تشغيل الـ Pod، فتغييره من
ConfigMap وحده لن يغيّر سلوك العميل الفعلي.

## قيم Secret

كل ملفات `secret.yaml` تحت هذا المجلد تحتوي **قيماً وهمية فقط** (`CHANGE_ME`)
لتشغيل محلي/اختبار. لا تُستخدَم في إنتاج فعلي — استبدلها عبر
`kubectl create secret` مباشرة أو أداة إدارة أسرار خارجية قبل أي نشر حقيقي.
