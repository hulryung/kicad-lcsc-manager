# JLCPCB API Integration - Stock and Pricing

## 문제 해결

이전 버전에서는 EasyEDA API만 사용했기 때문에 재고(stock)와 가격(price) 정보가 없었습니다.

**bom-extender** 프로젝트를 참고하여 **JLCPCB API**를 통합했습니다.

## 통합된 API 구조

플러그인은 이제 두 개의 API를 조합하여 완전한 정보를 제공합니다:

### 1. EasyEDA API
**용도**: 심볼/풋프린트 데이터
**엔드포인트**: `https://easyeda.com/api/products/{lcsc_id}/components`

**제공 정보**:
- 심볼 UUID (symbol conversion용)
- 풋프린트 UUID (footprint conversion용)
- 제품명 (예: RP2040)
- 제조사 (예: Raspberry Pi)
- 패키지 타입
- JLCPCB 파트 분류
- EasyEDA 전체 데이터 (converters용)

### 2. JLCPCB API (새로 추가!)
**용도**: 재고/가격 정보
**엔드포인트**: `https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList`

**제공 정보**:
- ✓ **재고 수량** (stockCount)
- ✓ **가격 정보** (componentPrices) - 수량별 티어
- ✓ **데이터시트 URL** (dataManualUrl)
- ✓ **제품 이미지 ID** (minImageAccessId)
- ✓ **상품 URL** (lcscGoodsUrl)
- 상세 설명 (describe)

## 코드 변경사항

### 1. API 클라이언트 (`plugins/lcsc_manager/api/lcsc_api.py`)

#### 새로 추가된 메서드: `_get_jlcpcb_info()`
```python
def _get_jlcpcb_info(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
    """JLCPCB API로 재고/가격 정보 가져오기"""
    response = self._make_request(
        method="POST",
        url=self.JLCPCB_SEARCH_URL,
        json_data={"keyword": lcsc_id}
    )

    # 재고, 가격, 데이터시트 등 추출
    return {
        "stock": stock,
        "price": prices,  # 수량별 가격 티어
        "datasheet": datasheet_url,
        "image": image_id,
        "url": product_url,
    }
```

#### 업데이트된 메서드: `search_component()`
```python
def search_component(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
    """EasyEDA와 JLCPCB API를 모두 호출하여 완전한 정보 제공"""

    # Step 1: EasyEDA에서 심볼/풋프린트 데이터
    easyeda_data = self._get_easyeda_component(lcsc_id)

    # Step 2: JLCPCB에서 재고/가격 데이터
    jlcpcb_data = self._get_jlcpcb_info(lcsc_id)

    # Step 3: 데이터 병합
    return merged_component_data
```

### 2. UI 업데이트 (`plugins/lcsc_manager/dialog.py`)

가격 표시 형식 개선:
```python
# 재고 표시
Stock: 40,315 units

# 가격 티어 표시
Pricing (per unit):
  1-9: $0.9565
  10-29: $0.8719
  30-99: $0.7937
  100-499: $0.7342
  500-999: $0.7091
  1,000+: $0.6982
```

## 테스트 결과

### C2040 (Raspberry Pi RP2040) 테스트

```bash
python3 test_integrated_api.py
```

**출력 결과**:
```
✓ Component found!

BASIC INFORMATION
LCSC ID: C2040
Name: RP2040
Manufacturer: Raspberry Pi(树莓派)
Manufacturer Part: RP2040
Package: LQFN-56_L7.0-W7.0-P0.4-EP
JLCPCB Class: Extended Part

STOCK & AVAILABILITY
Stock: 40,315 units

PRICING
  Tier 1:   1-9 units @ $0.956500
  Tier 2:  10-29 units @ $0.871900
  Tier 3:  30-99 units @ $0.793700
  Tier 4: 100-499 units @ $0.734200
  Tier 5: 500-999 units @ $0.709100
  Tier 6:  1,000+ units @ $0.698200

LINKS & RESOURCES
Datasheet: https://www.lcsc.com/datasheet/...pdf
Product URL: https://www.lcsc.com/product-detail/...html
Image: https://assets.jlcpcb.com/attachments/...

✓ ALL CHECKS PASSED!
```

## API Rate Limiting

두 개의 API를 호출하므로 rate limiting이 중요합니다:

- 각 API 호출 간격: 2초 (REQUEST_DELAY)
- 분당 최대 요청: 30회 (MAX_REQUESTS_PER_MINUTE)
- C2040 검색 시: 약 4초 소요 (EasyEDA + JLCPCB)

## KiCad에서 테스트

1. **KiCad 재시작** (모든 창 닫기)
2. KiCad PCB Editor 실행
3. 프로젝트 열기 (저장된 프로젝트)
4. **Tools → External Plugins → LCSC Manager**
5. "C2040" 검색

**예상 결과**:
```
LCSC Part Number: C2040
Name: RP2040
Manufacturer: Raspberry Pi(树莓派) (RP2040)
Package: LQFN-56_L7.0-W7.0-P0.4-EP
JLCPCB Class: Extended Part
Stock: 40,315 units

Pricing (per unit):
  1-9: $0.9565
  10-29: $0.8719
  30-99: $0.7937
  100-499: $0.7342
  500-999: $0.7091
  1,000+: $0.6982

Datasheet: https://www.lcsc.com/datasheet/...pdf
```

## 참고 자료

- **bom-extender 프로젝트**: https://github.com/hulryung/bom-extender
  - `/src/app/api/lcsc/route.ts` 파일이 JLCPCB API 사용법 제공
- **JLCPCB API**: 비공식 API (reverse-engineered)
  - POST 요청으로 keyword 전달
  - 재고, 가격, 데이터시트 정보 제공

## 변경된 파일

1. `plugins/lcsc_manager/api/lcsc_api.py`
   - `_get_jlcpcb_info()` 메서드 추가
   - `search_component()` 메서드 업데이트
   - JLCPCB_SEARCH_URL 엔드포인트 추가

2. `plugins/lcsc_manager/dialog.py`
   - 재고 표시 개선
   - 가격 티어 표시 형식 개선

3. 새로운 테스트 파일
   - `test_jlcpcb_api.py` - JLCPCB API 단독 테스트
   - `test_integrated_api.py` - 통합 API 테스트

## 향후 개선사항

현재 완료된 기능:
- ✅ 제품 정보 (이름, 제조사, 패키지)
- ✅ 재고 정보
- ✅ 가격 정보 (수량별 티어)
- ✅ 데이터시트 링크
- ✅ 상품 URL
- ✅ 이미지

아직 플레이스홀더인 기능:
- ⚠️ 실제 심볼 생성 (현재는 generic 2-pin)
- ⚠️ 실제 풋프린트 생성 (현재는 generic 2-pad SMD)
- ⚠️ 3D 모델 다운로드 (현재는 VRML placeholder)

다음 단계:
1. EasyEDA 데이터 파싱 및 실제 심볼 생성
2. EasyEDA 데이터 파싱 및 실제 풋프린트 생성
3. 3D 모델 다운로드 및 변환

## 커밋 메시지

```
Add JLCPCB API integration for stock and pricing

- Integrated JLCPCB API to fetch stock, pricing, and datasheet info
- Plugin now combines EasyEDA (symbols/footprints) + JLCPCB (stock/price)
- Enhanced UI to display stock quantity and price tiers
- Added comprehensive tests for integrated API

Based on bom-extender project implementation.

Example: C2040 now shows:
- Stock: 40,315 units
- Pricing: 6 tiers from $0.9565 to $0.6982
- Datasheet: Direct PDF link
- Product URL: LCSC product page
```
